"""Separate application/MCP bases; pinned offline extraction dependencies."""
import pathlib,subprocess,json,shutil,re,time
root=pathlib.Path(__file__).resolve().parents[2];folder=root/'tmp/public-web-build';folder.mkdir(exist_ok=True)
targets=[('ai-server-moara-gateway-1','moara-core:public-web-app-20261102','moara-core:pre-public-web-app-20261102'),
         ('ai-server-moara-legal-mcp-1','moara-core:public-web-mcp-20261102','moara-core:pre-public-web-mcp-20261102')]
files=['moara/gateway/orchestration.py','moara/identity/attendance.py','moara/identity/service.py',
 'moara/legal_mcp/catalog.py','moara/legal_mcp/web_search.py','moara/legal_mcp/server.py','moara/legal_mcp/web_recovery.py',
 'moara/gateway/web_research.py','moara/gateway/chat_api.py','moara/gateway/api.py','moara/gateway/chat_progress.py',
 'moara/gateway/legal_verification.py','moara/gateway/self_knowledge.py','moara/gateway/institutional.py']
shutil.copytree(root/'tmp/web-search-deps/wheels',folder/'wheels',dirs_exist_ok=True)
shutil.copyfile(root/'tmp/web-search-deps/requirements.lock',folder/'requirements.lock')
for name in files:
 target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,target)
for service,tag,base in targets:
 if subprocess.run(['docker','image','inspect',base],capture_output=True).returncode:
  image=subprocess.check_output(['docker','inspect',service,'--format','{{.Image}}'],text=True).strip();subprocess.run(['docker','tag',image,base],check=True)
 dockerfile='FROM '+base+'\nUSER root\nCOPY wheels /tmp/moara-web-wheels\nCOPY requirements.lock /tmp/moara-web-requirements.lock\nRUN python -m pip install --no-index --find-links=/tmp/moara-web-wheels --require-hashes -r /tmp/moara-web-requirements.lock && rm -rf /tmp/moara-web-wheels /tmp/moara-web-requirements.lock\n'
 for name in files:
  if service.endswith('legal-mcp-1') and not name.startswith('moara/legal_mcp/'):continue
  dockerfile+='COPY '+name+' /app/'+name+'\n'
 dockerfile+='USER 10001:10001\n';(folder/'Dockerfile').write_text(dockerfile)
 subprocess.run(['docker','build','--network','none','-t',tag,str(folder)],check=True)
tests=folder/'tests';shutil.copytree(root/'tmp/chat-stream-build/tests',tests,dirs_exist_ok=True)
for name in ['test_web_search.py','test_moara2.py','test_development_scope.py','test_legal_catalog.py']:shutil.copyfile(root/'moara/tests'/name,tests/name)
tag=targets[0][1];r=subprocess.run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL','-v',str(tests)+':/tests:ro','--entrypoint','python',tag,'-m','unittest','discover','-s','/tests','-v'],capture_output=True,text=True)
print(r.stdout+r.stderr,flush=True)
images={service:subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip() for service,tag,base in targets}
match=re.search(r'Ran (\d+) tests',r.stdout+r.stderr)
(root/'tmp/public-web-tests.json').write_text(json.dumps({'passed':r.returncode==0,'tests':int(match[1]) if match else None,'images':images}));r.check_returncode()
suffix=images[targets[0][0]].split(':')[1][:10];core='moara-public-web-app-stage-'+suffix;legal='moara-public-web-mcp-stage-'+suffix
for service,tag,base in reversed(targets):
 name=legal if service.endswith('legal-mcp-1') else core
 original=json.loads(subprocess.check_output(['docker','inspect',service]))[0]
 if subprocess.run(['docker','inspect',name],capture_output=True).returncode:
  networks=list(original['NetworkSettings']['Networks']);args=['docker','create','--name',name,'--network',networks[0],'--read-only','--tmpfs','/tmp:size=128m','--memory','1g','--cpus','2','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges:true']
  env=dict(v.split('=',1) for v in original['Config']['Env']);env.update(MOARA_SEARXNG_URL='http://moara-searxng:8080',MOARA_PUBLIC_WEB_SEARCH='true')
  if name==core:env.update(MOARA_BACKGROUND_JOBS='false',MOARA_LEGAL_MCP_URL='http://'+legal+':8076/mcp')
  for k,v in env.items():args+=['-e',k+'='+v]
  for m in original['Mounts']:
   if m['Destination'].startswith(('/run/secrets/','/app/legal_catalog/')):args+=['--mount',f"type=bind,src={m['Source']},dst={m['Destination']},readonly"]
  args+=[tag]+original['Config']['Cmd'];subprocess.run(args,capture_output=True,check=True)
  for network in networks[1:]:subprocess.run(['docker','network','connect',network,name],capture_output=True,check=True)
  if name==legal and 'moara-public-search' not in networks:subprocess.run(['docker','network','connect','moara-public-search',name],capture_output=True,check=True)
 subprocess.run(['docker','start',name],capture_output=True,check=True)
 for _ in range(40):
  port,path=(8076,'/health') if name==legal else (8075,'/api/v1/ready')
  ready=subprocess.run(['docker','exec',name,'python','-c',f"import urllib.request;assert urllib.request.urlopen('http://localhost:{port}{path}',timeout=3).status==200"],capture_output=True)
  if ready.returncode==0:break
  time.sleep(1)
 else:raise RuntimeError('Private candidate readiness failed')
(root/'tmp/public-web-stage.json').write_text(json.dumps({'core':core,'mcp':legal,'images':images}))
print(json.dumps({'core':core,'mcp':legal,'private_candidates_ready':True}))
