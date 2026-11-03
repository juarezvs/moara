import subprocess,json,collections
from pathlib import Path
r=json.loads(Path('/home/nutec/ai-server/docs/runtime/embedding-upload-validation-20261027.json').read_text())
logs=subprocess.check_output(['docker','logs','--since',r['started_at'],'ai-server-gateway-1'],stderr=subprocess.STDOUT).decode(errors='replace')
events=[]
for line in logs.splitlines():
 try:d=json.loads(line)
 except:continue
 if d.get('event')=='request' and d.get('route')!='/v1/embeddings':events.append({k:d.get(k) for k in ['route','status','elapsed_ms','client']})
print(json.dumps(events[-8:]))
