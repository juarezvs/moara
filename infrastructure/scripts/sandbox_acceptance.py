"""Synthetic runtime checks for bounded code execution and document tools."""
import importlib.util,json,subprocess
from pathlib import Path
ROOT=Path('/home/nutec/moara-platform-20261026')
spec=importlib.util.spec_from_file_location('sandbox',ROOT/'sandbox_worker.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
def image(name):return subprocess.check_output(['docker','image','inspect','-f','{{.Id}}',name],text=True).strip()
py=image('moara-core:platform-20261026');node=image('node:24-bookworm-slim');checks=[]
def check(name,value):
 checks.append({'name':name,'passed':bool(value)})
 if not value:raise AssertionError(name)
result=module.execute({'main.py':"print(17+25)"},'python',py,node)
check('python_execution',result['exit_code']==0 and result['output'].strip()=='42')
result=module.execute({'main.py':"""import socket, pathlib
try:
 socket.create_connection(('172.19.5.250',443),timeout=1)
 print('NETWORK_OPEN')
except OSError:print('NETWORK_DENIED')
print('SOCKET_ABSENT',not pathlib.Path('/var/run/docker.sock').exists())
try:pathlib.Path('/workspace/changed').write_text('x');print('WRITE_OPEN')
except OSError:print('WRITE_DENIED')
print('SECRETS_ABSENT',not pathlib.Path('/run/secrets/moara_db_password').exists())
"""},'python',py,node)
check('network_denied','NETWORK_DENIED' in result['output']);check('input_readonly','WRITE_DENIED' in result['output'])
check('no_docker_socket','SOCKET_ABSENT True' in result['output']);check('no_credentials','SECRETS_ABSENT True' in result['output'])
result=module.execute({'main.py':'while True: pass'},'python',py,node,timeout=3)
check('timeout_enforced',result['termination']=='timeout' and result['duration_seconds']<20)
result=module.execute({'main.py':"print('a'*200000)"},'python',py,node)
check('output_bounded',result['truncated'] and len(result['output'])<=65536)
result=module.execute({'main.ts':"const value: number = 42; console.log(value);"},'typescript',py,node)
check('typescript_execution',result['exit_code']==0 and '42' in result['output'])
check('no_sandbox_left',not subprocess.check_output(['docker','ps','-q','--filter','label=moara.sandbox.job'],text=True).strip())
print(json.dumps({'checks':checks,'synthetic_only':True,'production_modified':False}))
