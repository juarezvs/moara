set -eu
python3 - <<'PY'
import urllib.request,json,time
base='http://127.0.0.1:11434'
def call(path,body=None):
 return json.load(urllib.request.urlopen(urllib.request.Request(base+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'}),timeout=180))
start=time.monotonic()
result=call('/api/embed',{'model':'embeddinggemma:300m','input':['Validação sintética GPU '+str(i)+'. O prazo fictício é sete dias úteis.' for i in range(16)],'truncate':False,'keep_alive':-1,'options':{'num_thread':12,'num_gpu':999}})
print(json.dumps({'seconds':time.monotonic()-start,'vectors':len(result['embeddings']),'dimensions':len(result['embeddings'][0]),'residency':call('/api/ps')}),flush=True)
PY
docker exec moara-gpu-ollama ollama ps
