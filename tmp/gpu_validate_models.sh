set -eu
python3 - <<'PY'
import pathlib,json,hashlib,time
b=pathlib.Path('/home/nutec/moara-gpu-validation/models')
bad=[];count=0;total=0
for p in sorted((b/'blobs').glob('sha256-*')):
 h=hashlib.file_digest(p.open('rb'),'sha256').hexdigest();count+=1;total+=p.stat().st_size
 if h!=p.name.removeprefix('sha256-'):bad.append(p.name)
print(json.dumps({'validated_blobs':count,'bytes':total,'bad':bad}),flush=True)
if bad:raise SystemExit(1)
for p in b.glob('manifests*/**/*'):
 if p.is_file():
  m=json.loads(p.read_text())
  for layer in [m['config']]+m['layers']:
   f=b/'blobs'/layer['digest'].replace(':','-')
   assert f.exists() and f.stat().st_size==layer['size'],str(f)
print('All manifest dependencies present',flush=True)
PY
docker start moara-gpu-validation
python3 - <<'PY'
import urllib.request,json,time,pathlib
base='http://172.19.5.246:11435'
def call(path,body=None):
 r=urllib.request.Request(base+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
 return json.load(urllib.request.urlopen(r,timeout=120))
for i in range(30):
 try:tags=call('/api/tags')['models'];break
 except Exception:time.sleep(1)
else:raise RuntimeError('Ollama not ready')
for m in tags:
 name=m['name']
 if name.startswith('ai-fast-8k:') or name.startswith('moara-'):
  tmp='gpu-validation-'+name
  print('gpu_parameters',name,call('/api/create',{'model':tmp,'from':name,'parameters':{'num_gpu':-1},'stream':False}),flush=True)
  call('/api/copy',{'source':tmp,'destination':name})
print(json.dumps(call('/api/tags'),ensure_ascii=False),flush=True)
PY
nohup timeout 1200 nvidia-smi --query-gpu=timestamp,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw --format=csv -l 1 > /home/nutec/moara-gpu-validation/gpu-metrics.csv 2>&1 < /dev/null &
echo "gpu_metrics_pid=$!"
