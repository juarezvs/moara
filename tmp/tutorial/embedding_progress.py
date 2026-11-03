import subprocess,json,collections
from pathlib import Path
report=json.loads(Path('/home/nutec/ai-server/docs/runtime/embedding-upload-validation-20261027.json').read_text())
logs=subprocess.check_output(['docker','logs','--since',report['started_at'],'ai-server-gateway-1'],stderr=subprocess.STDOUT).decode(errors='replace')
counts=collections.Counter();elapsed=[]
for line in logs.splitlines():
 try:r=json.loads(line)
 except ValueError:continue
 if r.get('event')=='request' and r.get('route')=='/v1/embeddings' and r.get('client')=='webui':
  counts[str(r.get('status'))]+=1
  if r.get('status')==200:elapsed.append(r.get('elapsed_ms',0))
print(json.dumps({'embedding_statuses':dict(counts),'average_batch_ms':round(sum(elapsed)/len(elapsed)) if elapsed else None,'processing_status':report.get('processing_status')}))
