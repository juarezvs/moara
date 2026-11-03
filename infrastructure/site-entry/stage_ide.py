"""Start a private candidate without taking production jobs; preserve old candidates."""
import json,pathlib,subprocess,time
root=pathlib.Path(__file__).resolve().parents[2]
image='moara-core:ide-20261030'
def run(args):return subprocess.check_output(args,text=True,stderr=subprocess.PIPE).strip()
image_id=run(['docker','image','inspect',image,'--format','{{.Id}}'])
name='moara-ide-stage-'+image_id.split(':')[-1][:10]
if subprocess.run(['docker','inspect',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
    original=json.loads(run(['docker','inspect','ai-server-moara-gateway-1']))[0]
    args=['docker','create','--name',name,'--network','ai-server_frontend','--memory','1g','--cpus','2',
          '--read-only','--tmpfs','/tmp:size=128m','--cap-drop','ALL','--security-opt','no-new-privileges:true']
    env=dict(v.split('=',1) for v in original['Config']['Env']);env['MOARA_BACKGROUND_JOBS']='false'
    for k,v in env.items():args+=['-e',k+'='+v]
    for mount in original['Mounts']:
        if mount['Destination'].startswith('/run/secrets/'):
            args+=['--mount',f"type=bind,src={mount['Source']},dst={mount['Destination']},readonly"]
    args+=[image]+original['Config']['Cmd'];run(args)
    for network in original['NetworkSettings']['Networks']:
        if network!='ai-server_frontend':run(['docker','network','connect',network,name])
run(['docker','start',name])
for _ in range(30):
    try:
        status=json.loads(run(['docker','exec',name,'python','-c','import urllib.request;print(urllib.request.urlopen("http://localhost:8075/api/v1/ready",timeout=3).read().decode())']))
        assert status['status']=='ready';break
    except Exception:time.sleep(1)
else:raise RuntimeError('Candidate did not become ready')
(root/'tmp/ide-core-name.txt').write_text(name)
print(json.dumps({'candidate':name,'ready':True,'production_job_consumption':False,'ports_published':False}),flush=True)
