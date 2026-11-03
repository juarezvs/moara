import json,httpx,time
from moara.gateway.settings import Settings
s=Settings.load();report={'synthetic_only':True,'samples':[]}
with httpx.Client(trust_env=False,timeout=180) as c:
 for texts in [['Texto fictício '+str(i)+': o prazo é sete dias úteis.' for i in range(16)],['Alpha team replies in seven business days. '*100]]:
  for rep in range(2):
   start=time.monotonic();r=c.post('http://gateway:8000/v1/embeddings',headers={'Authorization':'Bearer '+s.llm_key},json={'model':'embedding','input':texts});r.raise_for_status();v=r.json()['data']
   assert len(v)==len(texts) and all(len(row['embedding'])==768 for row in v)
   report['samples'].append({'vectors':len(v),'dimensions':768,'repetition':rep,'seconds':time.monotonic()-start})
 for kind,base in [('primary','http://moara-gpu-tunnel:11434'),('embeddings','http://moara-gpu-tunnel:11435')]:
  rows=c.get(base+'/api/ps').json()['models'];report[kind]=rows
  assert len(rows)==1 and rows[0]['size_vram']==rows[0]['size'] and rows[0]['size']>0
print(json.dumps(report,ensure_ascii=False),flush=True)
