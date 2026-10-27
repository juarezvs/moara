import json,subprocess
from pathlib import Path
ROOT=Path('/home/nutec/ai-server');STAGE=Path('/home/nutec/moara-platform-20261026-r2');name='moara-platform-inference-relay'
obj=json.loads(subprocess.check_output(['docker','inspect','ai-server-gateway-1']))[0]
address=next(v['IPAddress'] for k,v in obj['NetworkSettings']['Networks'].items() if k.endswith('_inference'))
p=subprocess.run(['docker','inspect',name],capture_output=True)
if p.returncode==0:
 if json.loads(p.stdout)[0]['Config'].get('Labels',{}).get('moara.test')!='platform-inference':raise RuntimeError('unowned fixture')
 subprocess.run(['docker','rm','-f',name],check=True,capture_output=True)
args=['docker','run','-d','--name',name,'--label','moara.test=platform-inference','--network','moara-platform-qa-isolated','--network-alias','gateway',
 '--memory','256m','--cpus','1','--pids-limit','32','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true',
 '-e','UPSTREAM_IP='+address,'--mount',f'type=bind,source={STAGE}/moara/tests/inference_relay.py,target=/relay.py,readonly',
 '--mount',f'type=bind,source={ROOT}/secrets/moara_llm_key,target=/run/secrets/upstream,readonly',
 '--mount',f'type=bind,source={ROOT}/secrets/moara-platform-qa/moara_llm_key,target=/run/secrets/qa,readonly',
 'moara-core:platform-20261026-r2','python','/relay.py']
p=subprocess.run(args,capture_output=True)
if p.returncode:raise RuntimeError('relay_start_failed')
subprocess.run(['docker','network','connect','ai-server_inference',name],capture_output=True,check=True)
try:
 p=subprocess.run(['docker','exec','-i','moara-platform-qa-api','python','-'],input=(STAGE/'moara/tests/platform_real_inference.py').read_bytes(),capture_output=True,timeout=1500)
 print(p.stdout.decode());print(p.stderr.decode()[-4000:])
finally:subprocess.run(['docker','rm','-f',name],capture_output=True,check=True)
raise SystemExit(p.returncode)
