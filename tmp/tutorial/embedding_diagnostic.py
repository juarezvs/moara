import subprocess,json,collections
root='/home/nutec/ai-server'
code="""import json,os
from pathlib import Path
clients=json.loads(Path(os.environ.get('CLIENTS_FILE','/run/secrets/clients.json')).read_text())
print(json.dumps({'clients':[{'id':c['id'],'rpm':c.get('rpm',30),'embed':'embed' in c.get('scopes',[])} for c in clients]}))
"""
print(subprocess.check_output(['docker','exec','ai-server-gateway-1','python','-c',code],text=True))
code="""from open_webui.main import app
import json
keys=['RAG_EMBEDDING_ENGINE','RAG_EMBEDDING_MODEL','RAG_EMBEDDING_BATCH_SIZE','RAG_EMBEDDING_CONCURRENT_REQUESTS','CHUNK_SIZE','CHUNK_OVERLAP']
print(json.dumps({k:getattr(app.state.config,k,None) for k in keys},default=str))
"""
p=subprocess.run(['docker','exec','ai-server-webui-1','python','-c',code],capture_output=True,text=True,timeout=90)
for line in p.stdout.splitlines():
 if line.startswith('{'):print(line)
logs=subprocess.check_output(['docker','logs','--since','2h','ai-server-gateway-1'],stderr=subprocess.STDOUT).decode(errors='replace')
counts=collections.Counter();queues=0
for line in logs.splitlines():
 try:r=json.loads(line)
 except ValueError:continue
 if r.get('event')=='request' and r.get('route')=='/v1/embeddings':counts[(str(r.get('client')),str(r.get('status')))]+=1
 if r.get('event')=='inference_queue':queues+=1
print(json.dumps({'embedding_requests_last_2h':{'/'.join(k):v for k,v in counts.items()},'queue_events':queues}))
print(subprocess.check_output(['docker','inspect','-f','{{.Image}}','ai-server-gateway-1'],text=True).strip())
