import json,pathlib,subprocess,time,urllib.request
ROOT=pathlib.Path('/home/nutec/ai-server');WORK=ROOT/'tmp/gpu-production'
def run(args):return subprocess.check_output(args,text=True).strip()
cfg=json.loads(run(['sh',str(ROOT/'moara/infrastructure/scripts/compose.sh'),'config','--format','json']))
launcher=(ROOT/'tmp/gpu-validation/moara_gpu_test_app.py').read_text().replace('moara-validation-adapter','moara-gpu-stage-adapter')
(WORK/'stage_app.py').write_text(launcher)
def clone(original,name,image,env_update=None,extra=None,cmd=None):
 d=json.loads(run(['docker','inspect',original]))[0]
 args=['docker','create','--name',name,'--network','ai-server_frontend','--memory','1g','--cpus','2','--read-only','--tmpfs','/tmp:size=128m','--cap-drop','ALL','--security-opt','no-new-privileges:true']
 env=dict(x.split('=',1) for x in d['Config']['Env']);env.update(env_update or {})
 for k,v in env.items():args+=['-e',k+'='+str(v)]
 for m in d['Mounts']:
  if m['Destination'].startswith('/run/secrets/'):args+=['--mount',f"type=bind,src={m['Source']},dst={m['Destination']},readonly"]
 args+=extra or [];args+=[image]+(cmd or d['Config']['Cmd']);run(args)
 for net in ['ai-server_storage','ai-server_inference','ai-server_moara_control','ai-server_download']:run(['docker','network','connect',net,name])
 run(['docker','start',name])
clone('ai-server-gateway-1','moara-gpu-stage-adapter','ai-gateway:gpu-20261029',cfg['services']['gateway']['environment'])
clone('ai-server-moara-gateway-1','moara-gpu-stage-http','moara-core:gpu-20261029',extra=['-p','127.0.0.1:18075:8075','-v',str(WORK/'stage_app.py')+':/app/stage_app.py:ro'],cmd=['uvicorn','stage_app:app','--host','0.0.0.0','--port','8075','--workers','1','--no-access-log'])
for i in range(30):
 try:print(urllib.request.urlopen('http://127.0.0.1:18075/api/v1/ready',timeout=2).read().decode());break
 except Exception:time.sleep(1)
else:raise RuntimeError('Stage not ready')
