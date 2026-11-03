import subprocess,json,collections
from pathlib import Path
r=json.loads(Path('/home/nutec/ai-server/docs/runtime/embedding-upload-validation-20261027.json').read_text())
raw=subprocess.check_output(['docker','logs','--timestamps','--since',r['started_at'],'ai-server-gateway-1'],stderr=subprocess.STDOUT).decode(errors='replace')
errors=[];counts=collections.Counter();queues=[]
for line in raw.splitlines():
 try:stamp,body=line.split(' ',1);v=json.loads(body)
 except ValueError:continue
 if v.get('event')=='request':
  counts[(str(v.get('route')),str(v.get('client')),str(v.get('status')))]+=1
  if v.get('status')==429:errors.append({'at':stamp,'route':v.get('route'),'client':v.get('client'),'elapsed_ms':v.get('elapsed_ms')})
 if v.get('event')=='inference_queue':queues.append(v)
print(json.dumps({'errors':errors,'counts':{'/'.join(k):v for k,v in counts.items()},'queue_events':queues[-6:]}))
