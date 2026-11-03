"""Private MCP + application candidates with the same ACLs and no job workers."""
import pathlib,json,subprocess,time
root=pathlib.Path(__file__).resolve().parents[2];image='moara-core:legal-grounding-20261031'
suffix=subprocess.check_output(['docker','image','inspect',image,'--format','{{.Id}}'],text=True).strip().split(':')[1][:10]
legal='moara-legal-grounding-stage-'+suffix;core='moara-legal-app-grounding-stage-'+suffix
def clone(original_name,name,extra_env):
 if subprocess.run(['docker','inspect',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
  original=json.loads(subprocess.check_output(['docker','inspect',original_name]))[0]
  networks=list(original['NetworkSettings']['Networks'])
  args=['docker','create','--name',name,'--network',networks[0],'--read-only','--tmpfs','/tmp:size=128m',
   '--memory','1g' if name==core else '512m','--cpus','2','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges:true']
  env=dict(v.split('=',1) for v in original['Config']['Env']);env.update(extra_env)
  for k,v in env.items():args+=['-e',k+'='+v]
  for mount in original['Mounts']:
   if mount['Destination'].startswith('/run/secrets/'):
    args+=['--mount',f"type=bind,src={mount['Source']},dst={mount['Destination']},readonly"]
  args+=[image]+original['Config']['Cmd'];subprocess.run(args,check=True,stdout=subprocess.DEVNULL)
  for network in networks[1:]:subprocess.run(['docker','network','connect',network,name],check=True)
 subprocess.run(['docker','start',name],check=True,stdout=subprocess.DEVNULL)
clone('ai-server-moara-legal-mcp-1',legal,{})
clone('ai-server-moara-gateway-1',core,{'MOARA_BACKGROUND_JOBS':'false','MOARA_LEGAL_MCP_URL':'http://'+legal+':8076/mcp'})
for name,port,path in [(legal,8076,'/health'),(core,8075,'/api/v1/ready')]:
 for _ in range(40):
  r=subprocess.run(['docker','exec',name,'python','-c','import urllib.request;assert urllib.request.urlopen('+repr(f'http://localhost:{port}{path}')+',timeout=3).status==200'],capture_output=True)
  if r.returncode==0:break
  time.sleep(1)
 else:raise RuntimeError('Candidate readiness failed')
(root/'tmp/legal-grounding-stage.json').write_text(json.dumps({'mcp':legal,'core':core}))
print(json.dumps({'private_candidates_ready':True,'mcp':legal,'core':core,'ports_published':False,'background_jobs':False}))
