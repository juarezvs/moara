import json,subprocess,pathlib,time,urllib.request
ROOT=pathlib.Path('/home/nutec/ai-server')
WORK=ROOT/'tmp/gpu-validation';WORK.mkdir(parents=True,exist_ok=True)

def run(args):return subprocess.check_output(args,text=True).strip()
def clone(original,name,extra_env=None,extra_args=None,cmd=None):
 d=json.loads(run(['docker','inspect',original]))[0]
 env=dict(x.split('=',1) for x in d['Config']['Env'])
 env.update(extra_env or {})
 args=['docker','create','--name',name,'--network','ai-server_frontend','--memory','1g','--cpus','2','--pids-limit','128','--read-only','--tmpfs','/tmp:size=128m','--cap-drop','ALL','--security-opt','no-new-privileges:true']
 for k,v in env.items():args+=['-e',k+'='+v]
 for m in d['Mounts']:
  if m['Destination'].startswith('/run/secrets/'):
   args+=['--mount',f"type=bind,src={m['Source']},dst={m['Destination']},readonly"]
 args+=extra_args or []
 args+=[d['Image']]+(cmd or d['Config']['Cmd'])
 run(args)
 for net in ['ai-server_storage','ai-server_inference','ai-server_moara_control','ai-server_download']:
  run(['docker','network','connect',net,name])
 run(['docker','start',name]);print(name,'started',flush=True)

clone('ai-server-gateway-1','moara-validation-adapter',{'INFERENCE_BASE_URL':'http://172.19.5.246:11435','EMBEDDING_BASE_URL':'http://172.19.5.246:11435'})
clone('ai-server-moara-gateway-1','moara-validation-http',extra_args=['-p','127.0.0.1:18075:8075','-v',str(WORK/'moara_gpu_test_app.py')+':/app/moara_gpu_test_app.py:ro'],cmd=['uvicorn','moara_gpu_test_app:app','--host','0.0.0.0','--port','8075','--workers','1','--no-access-log'])
for n in range(30):
 try:
  print(urllib.request.urlopen('http://127.0.0.1:18075/api/v1/ready',timeout=2).read().decode());break
 except Exception:time.sleep(1)
else:raise RuntimeError('Validation Moara not ready')
