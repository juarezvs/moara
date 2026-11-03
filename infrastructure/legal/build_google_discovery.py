import pathlib,subprocess,json,shutil,secrets,time
root=pathlib.Path(__file__).resolve().parents[2]
def out(args):return subprocess.check_output(args,text=True,stderr=subprocess.PIPE).strip()
for service,tag in [('ai-server-moara-gateway-1','moara-core:pre-google-app-20261031'),('ai-server-moara-legal-mcp-1','moara-core:pre-google-mcp-20261031')]:
 if subprocess.run(['docker','image','inspect',tag],capture_output=True).returncode:subprocess.run(['docker','tag',out(['docker','inspect',service,'--format','{{.Image}}']),tag],check=True)
renderer=json.loads(out(['docker','inspect','ai-server-studio-renderer-1']))[0]
subprocess.run(['docker','tag',renderer['Image'],'moara-browser-base:source-discovery-20261031'],check=True)
profile=next(s[8:] for s in renderer['HostConfig']['SecurityOpt'] if s.startswith('seccomp='))
profile_path=root/'infrastructure/google-browser-seccomp.json';profile_path.write_text(profile)
key=root/'secrets/moara_google_browser_key'
if not key.exists():key.write_text(secrets.token_urlsafe(48));key.chmod(0o644)
folder=root/'tmp/google-discovery-build';folder.mkdir(exist_ok=True)
shutil.copytree(root/'moara/research_browser',folder/'moara/research_browser',dirs_exist_ok=True)
(folder/'browser.Dockerfile').write_text('FROM moara-browser-base:source-discovery-20261031\nWORKDIR /app\nCOPY moara/research_browser /app/moara/research_browser\nENV PYTHONPATH=/app HOME=/tmp\nCMD ["python3","-m","uvicorn","moara.research_browser.main:app","--host","0.0.0.0","--port","8077","--workers","1","--no-access-log"]\n')
subprocess.run(['docker','build','--network','none','-f',str(folder/'browser.Dockerfile'),'-t','moara-reference-browser:20261031',str(folder)],check=True)
shutil.copytree(root/'moara/legal_mcp',folder/'moara/legal_mcp',dirs_exist_ok=True)
(folder/'core.Dockerfile').write_text('FROM moara-core:pre-google-app-20261031\nCOPY moara/legal_mcp /app/moara/legal_mcp\nCOPY moara/research_browser /app/moara/research_browser\n')
subprocess.run(['docker','build','--network','none','-f',str(folder/'core.Dockerfile'),'-t','moara-core:google-discovery-20261031',str(folder)],check=True)
tests=folder/'tests';shutil.copytree(root/'tmp/jurisprudence-build/tests',tests,dirs_exist_ok=True)
for name in ['test_google_discovery.py','test_legal_catalog.py']:shutil.copyfile(root/'moara/tests'/name,tests/name)
subprocess.run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL','-v',str(tests)+':/tests:ro','--entrypoint','python','moara-core:google-discovery-20261031','-m','unittest','discover','-s','/tests','-v'],check=True)
for network,internal in [('ai-server_moara_search_stage',True),('ai-server_moara_research_browser',True),('ai-server_moara_search_egress',False)]:
 if subprocess.run(['docker','network','inspect',network],capture_output=True).returncode:subprocess.run(['docker','network','create',*(['--internal'] if internal else []),network],check=True,stdout=subprocess.DEVNULL)
browser_image=out(['docker','image','inspect','moara-reference-browser:20261031','--format','{{.Id}}']);suffix=browser_image.split(':')[1][:10];browser='moara-google-browser-stage-'+suffix+'-sandbox'
for name in out(['docker','ps','--format','{{.Names}}']).splitlines():
 if name.startswith('moara-google-browser-stage-') and name!=browser:subprocess.run(['docker','stop',name],check=True,capture_output=True)
if subprocess.run(['docker','inspect',browser],capture_output=True).returncode:
 args=['docker','create','--name',browser,'--network','ai-server_moara_search_stage','--network-alias','moara-google-browser','--read-only','--tmpfs','/tmp:size=512m,mode=1777','--shm-size','256m','--memory','1200m','--cpus','1.5','--pids-limit','256','--cap-drop','ALL','--cap-add','SYS_CHROOT','--security-opt','no-new-privileges:true','--security-opt','seccomp='+str(profile_path),'--mount',f'type=bind,src={key},dst=/run/secrets/moara_google_browser_key,readonly','moara-reference-browser:20261031']
 subprocess.run(args,check=True,stdout=subprocess.DEVNULL);subprocess.run(['docker','network','connect','ai-server_moara_search_egress',browser],check=True)
subprocess.run(['docker','start',browser],check=True,stdout=subprocess.DEVNULL)
image='moara-core:google-discovery-20261031';suffix=out(['docker','image','inspect',image,'--format','{{.Id}}']).split(':')[1][:10]
mcp='moara-google-mcp-stage-'+suffix;core='moara-google-app-stage-'+suffix
def clone(original_name,name,extra):
 if subprocess.run(['docker','inspect',name],capture_output=True).returncode:
  original=json.loads(out(['docker','inspect',original_name]))[0];networks=list(original['NetworkSettings']['Networks'])
  args=['docker','create','--name',name,'--network',networks[0],'--read-only','--tmpfs','/tmp:size=128m','--memory','1g','--cpus','2','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges:true']
  env=dict(v.split('=',1) for v in original['Config']['Env']);env.update(extra)
  for k,v in env.items():args+=['-e',k+'='+v]
  for mount in original['Mounts']:
   if mount['Destination'].startswith('/run/secrets/'):args+=['--mount',f"type=bind,src={mount['Source']},dst={mount['Destination']},readonly"]
  if name==mcp:args+=['--mount',f'type=bind,src={key},dst=/run/secrets/moara_google_browser_key,readonly']
  args+=[image]+original['Config']['Cmd'];subprocess.run(args,check=True,stdout=subprocess.DEVNULL)
  for network in networks[1:]:subprocess.run(['docker','network','connect',network,name],check=True)
  if name==mcp:subprocess.run(['docker','network','connect','ai-server_moara_search_stage',name],check=True)
 subprocess.run(['docker','start',name],check=True,stdout=subprocess.DEVNULL)
clone('ai-server-moara-legal-mcp-1',mcp,{'MOARA_REFERENCE_BROWSER_URL':'http://moara-google-browser:8077/references'})
clone('ai-server-moara-gateway-1',core,{'MOARA_BACKGROUND_JOBS':'false','MOARA_LEGAL_MCP_URL':'http://'+mcp+':8076/mcp'})
for name,port,path in [(browser,8077,'/health'),(mcp,8076,'/health'),(core,8075,'/api/v1/ready')]:
 for _ in range(35):
  r=subprocess.run(['docker','exec',name,'python3','-c',f"import urllib.request;assert urllib.request.urlopen('http://localhost:{port}{path}',timeout=3).status==200"],capture_output=True)
  if not r.returncode:break
  time.sleep(1)
 else:raise RuntimeError('Candidate readiness failed: '+name)
result={'browser':browser,'mcp':mcp,'core':core,'image':out(['docker','image','inspect',image,'--format','{{.Id}}']),'browser_image':browser_image}
(root/'tmp/google-discovery-stage.json').write_text(json.dumps(result));print(json.dumps({'private_candidates_ready':True,'ports_published':False,**result}))
