set -eu
python3 - <<'PY'
import pathlib,shutil,urllib.request,json
b=pathlib.Path('/home/nutec/moara-gpu-validation/models')
for p in (b/'manifests-v2/ollama.com/library').glob('*/*'):
 target=b/'manifests/registry.ollama.ai/library'/p.relative_to(b/'manifests-v2/ollama.com/library')
 target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
base='http://172.19.5.246:11435'
def call(path,body=None):
 return json.load(urllib.request.urlopen(urllib.request.Request(base+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'}),timeout=120))
tags=call('/api/tags')['models']
for m in tags:
 name=m['name']
 if name.startswith('ai-fast-8k:') or name.startswith('moara-'):
  tmp='gpu-validation-'+name
  print(name,call('/api/create',{'model':tmp,'from':name,'parameters':{'num_gpu':-1},'stream':False}),flush=True)
  call('/api/copy',{'source':tmp,'destination':name})
print('models',[(m['name'],m['size']) for m in call('/api/tags')['models']],flush=True)
PY
