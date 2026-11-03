import subprocess,json,pathlib,time
WORK=pathlib.Path('/home/nutec/ai-server/tmp/gpu-validation')
def run(args):return subprocess.check_output(args,text=True).strip()
run(['docker','cp','ai-server-gateway-1:/app/app.py',str(WORK/'gpu_adapter_app.py')])
p=WORK/'gpu_adapter_app.py';code=p.read_text()
for a,b in [("'num_gpu':0","'num_gpu':-1"),("'num_gpu': 0","'num_gpu': -1"),('"num_gpu": 0','"num_gpu": -1')]:code=code.replace(a,b)
p.write_text(code)
d=json.loads(run(['docker','inspect','ai-server-gateway-1']))[0]
env=dict(x.split('=',1) for x in d['Config']['Env']);env.update(INFERENCE_BASE_URL='http://172.19.5.246:11435',EMBEDDING_BASE_URL='http://172.19.5.246:11435')
args=['docker','create','--name','moara-validation-embeddings','--network','ai-server_frontend','--memory','1g','--cpus','2','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL','--security-opt','no-new-privileges:true']
for k,v in env.items():args+=['-e',k+'='+v]
for m in d['Mounts']:
 if m['Destination'].startswith('/run/secrets/'):args+=['--mount',f"type=bind,src={m['Source']},dst={m['Destination']},readonly"]
args+=['-v',str(p)+':/app/app.py:ro',d['Image']]+d['Config']['Cmd'];run(args)
for net in ['ai-server_storage','ai-server_download']:run(['docker','network','connect',net,'moara-validation-embeddings'])
run(['docker','start','moara-validation-embeddings']);time.sleep(3)
code='''import httpx,json,time,math
from moara.gateway.settings import Settings
s=Settings.load();headers={'Authorization':'Bearer '+s.llm_key}
texts=['Documento inteiramente fictício '+str(i)+': prazo de cinco dias úteis para a equipe Alfa responder ao pedido.' for i in range(16)]
results={};vectors={}
with httpx.Client(trust_env=False,timeout=180) as c:
 for mode,base in [('cpu','http://gateway:8000'),('gpu','http://moara-validation-embeddings:8000')]:
  results[mode]=[]
  for rep in range(3):
   start=time.monotonic();r=c.post(base+'/v1/embeddings',headers=headers,json={'model':'embedding','input':texts});elapsed=time.monotonic()-start;r.raise_for_status()
   value=r.json();v=[x['embedding'] for x in value['data']];vectors[mode]=v
   assert len(v)==16 and all(len(x)==768 and all(math.isfinite(n) for n in x) for x in v)
   results[mode].append({'repetition':rep,'seconds':elapsed,'vectors':len(v),'dimensions':len(v[0])})
cosines=[];diff=0
for a,b in zip(vectors['cpu'],vectors['gpu']):
 cosines.append(sum(x*y for x,y in zip(a,b))/(math.sqrt(sum(x*x for x in a))*math.sqrt(sum(y*y for y in b))))
 diff=max(diff,max(abs(x-y) for x,y in zip(a,b)))
print(json.dumps({'synthetic_only':True,'samples':results,'min_cosine':min(cosines),'max_abs_difference':diff,'compatible':min(cosines)>.999}))
'''
r=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-'],input=code,text=True,capture_output=True,timeout=900)
print(r.stdout,flush=True)
if r.returncode:print(r.stderr[-2000:]);raise SystemExit(r.returncode)
report=json.loads(r.stdout.strip().splitlines()[-1]);pathlib.Path('/home/nutec/ai-server/docs/runtime/gpu-validation-embeddings.json').write_text(json.dumps(report,indent=2))
