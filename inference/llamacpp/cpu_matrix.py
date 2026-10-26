"""CPU-only isolated comparison using the same installed Qwen GGUF, no downloads."""
import datetime,hashlib,json,os,secrets,subprocess,time
from pathlib import Path
ROOT=Path('/home/nutec/ai-server')
os.umask(0o077)
env=dict(line.split('=',1) for line in (ROOT/'infrastructure/.env').read_text().splitlines() if '=' in line)
nonce=secrets.token_hex(6);label='moara.benchmark='+nonce
report={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'synthetic short prompts; cold and warm samples; not a production SLA or legal-quality evaluation','production_changed':False,'samples':[],'configurations':[]}
out=ROOT/'docs/runtime/moara-cpu-matrix-20261026.json'
def run(args,timeout=600):
 r=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
 if r.returncode:raise RuntimeError('Command failed: '+args[0]+'; '+r.stderr[-1500:])
 return r.stdout.strip()
reader="""import json,hashlib
from pathlib import Path
p=Path('/models/models/manifests/registry.ollama.ai/library/qwen2.5-coder/7b-instruct-q4_K_M')
manifest=json.loads(p.read_text());layer=next(x for x in manifest['layers'] if x['mediaType']=='application/vnd.ollama.image.model')
model=Path('/models/models/blobs')/layer['digest'].replace(':','-')
assert model.open('rb').read(4)==b'GGUF'
h=hashlib.sha256()
with model.open('rb') as f:
 for block in iter(lambda:f.read(8388608),b''):h.update(block)
assert 'sha256:'+h.hexdigest()==layer['digest']
print(json.dumps({'path':str(model),'sha256':h.hexdigest(),'bytes':model.stat().st_size,'manifest_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'license_layers':[x['digest'] for x in manifest['layers'] if x['mediaType'].endswith('.license')]}))
"""
report['artifact']=json.loads(run(['docker','run','--rm','--label',label,'--pull=never','--network','none','--read-only','--memory','256m','--cpus','1','--cap-drop','ALL','--security-opt','no-new-privileges:true','--mount','type=volume,src=ai-server_ollama,dst=/models,readonly',env['PYTHON_IMAGE'],'python','-c',reader]))
ollama_image=run(['docker','inspect','--format','{{.Image}}','ai-server-ollama-1'])
llama_image=(ROOT/'inference/llamacpp/image.lock').read_text().strip()
client=r"""
import json,time,urllib.request,sys
backend,threads,context,prompt=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),sys.argv[4]
start=time.monotonic();first=None;pieces=[];usage={}
if backend=='ollama':
 url='http://127.0.0.1:11434/api/chat'
 payload={'model':'qwen2.5-coder:7b-instruct-q4_K_M','messages':[{'role':'user','content':prompt}],'stream':True,'keep_alive':'10m','options':{'num_thread':threads,'num_ctx':context,'num_gpu':0,'num_predict':48,'temperature':0,'seed':42}}
else:
 url='http://127.0.0.1:8081/v1/chat/completions'
 payload={'model':'benchmark','messages':[{'role':'user','content':prompt}],'stream':True,'stream_options':{'include_usage':True},'max_tokens':48,'temperature':0,'seed':42}
request=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=240) as response:
 for raw in response:
  line=raw.decode().strip()
  if not line or line=='data: [DONE]':continue
  if backend=='ollama':
   event=json.loads(line);piece=event.get('message',{}).get('content','')
   if event.get('done'):usage=event
  else:
   if not line.startswith('data:'):continue
   event=json.loads(line[5:]);piece=''.join(c.get('delta',{}).get('content','') or '' for c in event.get('choices',[]))
   if event.get('usage'):usage=event['usage']
  if piece and first is None:first=time.monotonic()-start
  pieces.append(piece)
elapsed=time.monotonic()-start;tokens=usage.get('eval_count',usage.get('completion_tokens',0))
text=''.join(pieces)
print(json.dumps({'ttft_seconds':first,'elapsed_seconds':elapsed,'output_tokens':tokens,'prompt_tokens':usage.get('prompt_eval_count',usage.get('prompt_tokens')),'generation_tokens_per_second':tokens/(usage['eval_duration']/1e9) if backend=='ollama' and usage.get('eval_duration') else tokens/max(.001,elapsed-(first or 0)),'answer':text,'backend_timings':{k:usage[k] for k in ['load_duration','prompt_eval_duration','eval_duration'] if k in usage}}))
"""
configs=[('ollama',12,4096,None),('ollama',24,4096,None),('ollama',48,4096,None),('ollama',12,8192,None),('llama.cpp',12,4096,None),('llama.cpp',12,4096,'distribute'),('llama.cpp',24,4096,'distribute'),('llama.cpp',48,4096,'distribute'),('llama.cpp',12,8192,'distribute')]
for index,(backend,threads,context,numa) in enumerate(configs):
 name='moara-cpu-'+nonce
 cfg={'backend':backend,'threads':threads,'context':context,'numa':numa or 'default','cpu_quota':24,'memory_limit_gib':16,'image':ollama_image if backend=='ollama' else llama_image}
 try:
  args=['docker','run','-d','--pull=never','--name',name,'--label',label,'--network','none','--read-only','--tmpfs','/tmp:size=128m,mode=1777','--memory','16g','--memory-swap','16g','--cpus','24','--pids-limit','256','--cap-drop','ALL','--security-opt','no-new-privileges:true','--mount','type=volume,src=ai-server_ollama,dst=/models,readonly']
  if backend=='ollama':
   args+=['--tmpfs','/root/.ollama:size=16m','-e','OLLAMA_MODELS=/models/models','-e','OLLAMA_HOST=127.0.0.1:11434','-e','OLLAMA_NO_CLOUD=1','-e','OLLAMA_NUM_PARALLEL=1','-e','OLLAMA_MAX_LOADED_MODELS=1',ollama_image]
  else:
   args+=[llama_image,'-m',report['artifact']['path'],'--host','127.0.0.1','--port','8081','-c',str(context),'-t',str(threads),'-tb',str(threads),'-ngl','0','--parallel','1','--alias','benchmark']
   if numa:args+=['--numa',numa]
  run(args)
  port=11434 if backend=='ollama' else 8081;route='/api/tags' if backend=='ollama' else '/health'
  helper=['docker','run','--rm','--pull=never','--label',label,'--network','container:'+name,'--memory','256m','--cpus','1','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true',env['PYTHON_IMAGE'],'python','-c']
  for attempt in range(90):
   ready=subprocess.run(helper+[f"import urllib.request;urllib.request.urlopen('http://127.0.0.1:{port}{route}',timeout=2)"],capture_output=True)
   if ready.returncode==0:break
   time.sleep(2)
  else:raise RuntimeError('benchmark_runtime_not_ready')
  for repetition in range(2):
   sample=json.loads(run(helper+[client,backend,str(threads),str(context),'Responda somente um JSON válido com a chave resultado e o valor da soma de 17 e 25.'],timeout=300))
   try:sample['json_arithmetic_passed']=json.loads(sample['answer'])=={'resultado':42}
   except Exception:sample['json_arithmetic_passed']=False
   sample.update(cfg,repetition=repetition)
   sample['memory_sample']=run(['docker','stats','--no-stream','--format','{{.MemUsage}}',name])
   report['samples'].append(sample)
  cfg['completed']=True
 except Exception as error:cfg.update(completed=False,error=str(error)[:1500])
 finally:
  existing=subprocess.run(['docker','inspect',name],capture_output=True,text=True)
  if existing.returncode==0:
   obj=json.loads(existing.stdout)[0]
   if obj['Config']['Labels'].get('moara.benchmark')!=nonce:raise RuntimeError('benchmark_name_collision')
   run(['docker','rm','-f',name])
  report['configurations'].append(cfg);out.write_text(json.dumps(report,indent=2))
  print(json.dumps({'configuration':index+1,'of':len(configs),**cfg}),flush=True)
report['completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();out.write_text(json.dumps(report,indent=2))
print(json.dumps({'report':str(out),'samples':len(report['samples']),'completed':sum(c['completed'] for c in report['configurations'])}))
