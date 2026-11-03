import pathlib,subprocess,json,time
root=pathlib.Path(__file__).resolve().parents[2]
command=['sh',str(root/'moara/infrastructure/scripts/compose.sh'),'-f','moara/infrastructure/gpu-tls-compose.yml']
subprocess.run(command+['up','-d','--no-deps','moara-gpu-tunnel-tls'],cwd=root,check=True)
cfg=json.loads(subprocess.check_output(command+['config','--format','json'],cwd=root))
original=json.loads(subprocess.check_output(['docker','inspect','ai-server-gateway-1']))[0]
name='moara-gateway-mtls-stage-20261030'
if subprocess.run(['docker','inspect',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
    networks=list(original['NetworkSettings']['Networks'])
    args=['docker','create','--name',name,'--network',networks[0],'--read-only','--tmpfs','/tmp:size=128m',
        '--cap-drop','ALL','--security-opt','no-new-privileges:true','--memory','1g','--cpus','2']
    env=dict(v.split('=',1) for v in original['Config']['Env']);env.update(cfg['services']['gateway']['environment'])
    for key,value in env.items():args+=['-e',key+'='+str(value)]
    for mount in original['Mounts']:
        if mount['Destination'].startswith('/run/secrets/'):
            args+=['-v',mount['Source']+':'+mount['Destination']+':ro']
    for key in ['moara_gpu_ca','moara_gpu_client_cert','moara_gpu_client_key']:
        args+=['-v',cfg['secrets'][key]['file']+':/run/secrets/'+key+':ro']
    args+=['ai-gateway:mtls-20261030']+original['Config']['Cmd']
    subprocess.run(args,check=True,stdout=subprocess.DEVNULL)
    for network in networks[1:]:subprocess.run(['docker','network','connect',network,name],check=True)
subprocess.run(['docker','start',name],check=True,stdout=subprocess.DEVNULL)
for _ in range(20):
    status=subprocess.run(['docker','exec',name,'python','-c','import urllib.request;print(urllib.request.urlopen("http://localhost:8000/health").status)'],capture_output=True)
    if status.returncode==0:break
    time.sleep(1)
else:raise RuntimeError('TLS gateway candidate not ready')
print('PRIVATE_MTLS_GATEWAY_READY')
