"""Rootless Docker execution worker. No service ports, socket mounts, or shell interpolation."""
import argparse,json,os,re,signal,subprocess,tempfile,threading,time,uuid
from pathlib import Path
LABEL='moara.sandbox.job'
def command(args,**kwargs):return subprocess.run(args,capture_output=True,timeout=20,**kwargs)
def validate(files):
 if not isinstance(files,dict) or len(files)>64:raise ValueError('invalid_files')
 total=0
 for name,value in files.items():
  if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_. /-]{1,180}',name) or any(p in ('','..','.') or p.startswith('.') for p in name.split('/')):raise ValueError('invalid_path')
  if not isinstance(value,str) or len(value.encode())>200000:raise ValueError('file_limit')
  total+=len(value.encode())
 if total>1000000:raise ValueError('project_limit')
def owned_stop(name,identifier):
 p=command(['docker','inspect','-f','{{json .Config.Labels}}',name],text=True)
 if p.returncode==0 and json.loads(p.stdout).get(LABEL)==identifier:command(['docker','rm','-f',name])
def execute(files,language,python_image,node_image,checkpoint=lambda:True,timeout=30):
 validate(files);identifier=str(uuid.uuid4());name='moara-sandbox-'+identifier
 image=python_image if language in ('python','fastapi') else node_image
 if not re.fullmatch(r'sha256:[0-9a-f]{64}',image):raise ValueError('immutable_image_required')
 entry='main.py' if language in ('python','fastapi') else 'main.ts'
 if entry not in files:raise ValueError('entrypoint_required')
 output=bytearray();truncated=False;reason=None;started=time.monotonic()
 with tempfile.TemporaryDirectory(prefix='moara-sandbox-') as folder:
  root=Path(folder);root.chmod(0o755)
  for name_in,content in files.items():
   path=root/name_in;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding='utf-8');path.chmod(0o444)
  for path in root.rglob('*'):
   if path.is_dir():path.chmod(0o755)
  argv=['docker','run','--name',name,'--label',LABEL+'='+identifier,'--network','none','--ipc','none',
   '--memory','256m','--memory-swap','256m','--cpus','1','--pids-limit','32','--ulimit','nofile=64:64',
   '--cap-drop','ALL','--security-opt','no-new-privileges:true','--read-only','--user','10001:10001',
   '--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=16m','--log-driver','none',
   '--mount',f'type=bind,source={root},target=/workspace,readonly','-w','/workspace',
   '-e','HOME=/tmp','-e','PYTHONDONTWRITEBYTECODE=1',image]
  ttl=max(1,min(30,int(timeout)))
  argv+=['timeout','--signal=KILL',str(ttl)+'s']
  argv+=['python','-I','-B','/workspace/main.py'] if language in ('python','fastapi') else ['node','--disable-proto=throw','/workspace/main.ts']
  proc=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  def drain():
   nonlocal truncated
   while True:
    chunk=proc.stdout.read(4096)
    if not chunk:break
    space=65536-len(output);output.extend(chunk[:max(0,space)])
    if len(chunk)>space:truncated=True
  reader=threading.Thread(target=drain,daemon=True);reader.start()
  try:
   while proc.poll() is None:
    if time.monotonic()-started>timeout:reason='timeout';break
    if not checkpoint():reason='cancelled_or_revoked';break
    time.sleep(2)
   if reason:owned_stop(name,identifier)
   try:code=proc.wait(timeout=10)
   except subprocess.TimeoutExpired:proc.kill();code=proc.wait()
   reader.join(timeout=5)
   if reason is None and code in (124,137) and time.monotonic()-started>=ttl:reason='timeout'
  finally:owned_stop(name,identifier)
 return {'exit_code':code,'output':output.decode('utf-8',errors='replace'),'truncated':truncated,
  'termination':reason,'duration_seconds':round(time.monotonic()-started,3),'network':'none','memory_mib':256,'cpu_limit':1,
  'runtime_image':image,'isolation':'rootless_docker_default_seccomp','requires_review':True}
def bridge(api,request):
 p=command(['docker','exec','-i',api,'python','-m','moara.gateway.platform_sandbox_bridge'],input=json.dumps(request).encode())
 if p.returncode:raise RuntimeError('bridge_unavailable')
 return json.loads(p.stdout)
def main():
 def terminate(*_):raise SystemExit(0)
 signal.signal(signal.SIGTERM,terminate)
 parser=argparse.ArgumentParser();parser.add_argument('--api',default='ai-server-moara-gateway-1');parser.add_argument('--once',action='store_true');args=parser.parse_args()
 def image(name):
  p=command(['docker','image','inspect','-f','{{.Id}}',name],text=True)
  if p.returncode:raise RuntimeError('sandbox_image_missing')
  return p.stdout.strip()
 python_image=image('moara-core:platform-20261026');node_image=image('node:24-bookworm-slim')
 while True:
  try:
   row=bridge(args.api,{'mode':'claim'})
   if row.get('available'):
    result=execute(row['files'],row['language'],python_image,node_image,lambda:bridge(args.api,{'mode':'check','id':row['id']}).get('available',False))
    bridge(args.api,{'mode':'finish','id':row['id'],'result':result})
  except Exception:print('sandbox_operation_failed',flush=True)
  if args.once:return
  time.sleep(3)
if __name__=='__main__':main()
