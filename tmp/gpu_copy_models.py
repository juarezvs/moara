import subprocess,shlex,time,json
from gpu_remote import gpu,source

c=gpu()
_,listing,_=c.exec_command("python3 -c \"import pathlib,json; b=pathlib.Path('/home/nutec/moara-gpu-validation/models'); print(json.dumps({str(p.relative_to(b)):p.stat().st_size for p in b.rglob('*') if p.is_file()}))\"")
existing=json.loads(listing.read().decode())
code='existing='+repr(existing)+'\n'+'''import tarfile,pathlib,json,sys
base=pathlib.Path('/home/nutec/.local/share/docker/volumes/ai-server_ollama/_data/models')
names=['ai-fast-8k/latest','qwen2.5-coder/7b-instruct-q4_K_M','embeddinggemma/300m','gemma4/12b-it-q4_K_M']
for p in base.glob('manifests-v2/ollama.com/library/moara-*/*'):
 if any(x in str(p) for x in ['moara-60c6b63c-','moara-63af8a56-']): names.append('/'.join(p.parts[-2:]))
paths=set()
for n in names:
 p=base/'manifests/registry.ollama.ai/library'/n
 if not p.exists(): p=base/'manifests-v2/ollama.com/library'/n
 paths.add(p)
 m=json.loads(p.read_text())
 for layer in [m['config']]+m['layers']: paths.add(base/'blobs'/layer['digest'].replace(':','-'))
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|',dereference=True) as tar:
 for p in sorted(paths):
  rel=str(p.relative_to(base))
  if rel.startswith('blobs/') and existing.get(rel)==p.stat().st_size: continue
  tar.add(p,arcname=rel,recursive=False)
'''
s=c.open_sftp()
for d in ['/home/nutec/moara-gpu-validation','/home/nutec/moara-gpu-validation/models']:
 try:s.mkdir(d)
 except OSError:pass
s.close()
i,o,e=c.exec_command('tar -xf - -C /home/nutec/moara-gpu-validation/models',timeout=1800)
p=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','nutec@172.19.5.250','python3 -c '+shlex.quote(code)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
start=time.monotonic(); total=0;last=start
while True:
 chunk=p.stdout.read(1024*1024)
 if not chunk:break
 i.write(chunk);total+=len(chunk)
 if time.monotonic()-last>15:
  print(json.dumps({'copied_gib':round(total/2**30,2),'seconds':round(time.monotonic()-start)}),flush=True);last=time.monotonic()
i.flush();i.channel.shutdown_write()
print(o.read().decode(),e.read().decode());rc=o.channel.recv_exit_status();c.close()
err=p.stderr.read().decode();sr=p.wait()
print(json.dumps({'bytes':total,'seconds':time.monotonic()-start,'source_rc':sr,'target_rc':rc}),err,flush=True)
if sr or rc:raise SystemExit(1)
