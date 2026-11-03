import pathlib,base64,json,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from gpu_remote import source,gpu
ROOT=pathlib.Path(__file__).resolve().parents[2]
names=['gateway/fastapi/app.py','gateway/fastapi/gpu_backend.py','moara/gateway/chat_api.py','moara/gateway/software_routing.py','moara/infrastructure/scripts/compose.sh','moara/infrastructure/gpu-compose.yml','tests/operations/test_gpu_backend.py']
names += ['infrastructure/gpu/'+p.name for p in (ROOT/'infrastructure/gpu').iterdir() if p.is_file()]
names += ['tmp/gpu-production/prepare_source.py','tmp/gpu-production/build_source.py']
payload={n:base64.b64encode((ROOT/n).read_bytes()).decode() for n in names}
script='''python3 - <<'PY'
import pathlib,json,base64,tarfile,os
os.umask(0o077)
r=pathlib.Path('/home/nutec/ai-server')
b=r/'backups/gpu-production-config-20261029.tar.gz'
if not b.exists():
 with tarfile.open(b,'w:gz') as tar:
  for name in ['gateway/fastapi/app.py','moara/gateway/chat_api.py','moara/gateway/software_routing.py','moara/infrastructure/scripts/compose.sh']:
   tar.add(r/name,arcname=name)
files=json.loads(PAYLOAD)
for name,data in files.items():
 p=r/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(data));p.chmod(0o644)
PY
python3 /home/nutec/ai-server/tmp/gpu-production/prepare_source.py
'''.replace('PAYLOAD',repr(json.dumps(payload)))
result=json.loads(source(script).strip().splitlines()[-1])
c=gpu();public=c.get_transport().get_remote_server_key()
known='172.19.5.246 '+public.get_name()+' '+public.get_base64()+'\n'
code='''python3 - <<'PY'
from pathlib import Path
p=Path('/home/nutec/ai-server/secrets/moara_gpu_known_hosts')
if p.exists():p.chmod(0o600)
p.write_text(KNOWN);p.chmod(0o444)
PY
'''.replace('KNOWN',repr(known))
source(code)
s=c.open_sftp()
try:s.mkdir('/home/nutec/moara-gpu-install')
except OSError:pass
for p in (ROOT/'infrastructure/gpu').iterdir():
 if p.is_file():s.put(str(p),'/home/nutec/moara-gpu-install/'+p.name)
with s.file('/home/nutec/moara-gpu-install/tunnel.pub','w') as f:f.write(result['public_key']+'\n')
s.close();c.close()
print('Source backup, files, restricted key and GPU installation files prepared')
