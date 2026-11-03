import json,pathlib,subprocess,time,urllib.request
root=pathlib.Path('/home/nutec/ai-server')
def run(args):return subprocess.check_output(args,text=True).strip()
d=json.loads(run(['docker','inspect','ai-server-moara-gateway-1']))[0]
name='moara-legal-stage-http'
args=['docker','create','--name',name,'--network','ai-server_frontend','--memory','1g','--cpus','2',
      '--read-only','--tmpfs','/tmp:size=128m','--cap-drop','ALL','--security-opt','no-new-privileges:true',
      '-p','127.0.0.1:18076:8075']
for env in d['Config']['Env']:args+=['-e',env]
for mount in d['Mounts']:
    if mount['Destination'].startswith('/run/secrets/'):
        args+=['--mount',f"type=bind,src={mount['Source']},dst={mount['Destination']},readonly"]
args+=['--mount',f'type=bind,src={root}/secrets/moara_legal_key,dst=/run/secrets/moara_legal_key,readonly',
       'moara-core:legal-20261030']+d['Config']['Cmd']
run(args)
for net in ['ai-server_storage','ai-server_inference','ai-server_moara_control']:run(['docker','network','connect',net,name])
run(['docker','start',name])
for i in range(30):
    try:
        print(run(['docker','exec',name,'python','-c','import urllib.request;print(urllib.request.urlopen("http://localhost:8075/api/v1/ready",timeout=2).read().decode())']));break
    except Exception:time.sleep(1)
else:raise RuntimeError('Legal stage not ready')
