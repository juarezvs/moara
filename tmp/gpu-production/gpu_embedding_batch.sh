set -eu
python3 - <<'PY'
import urllib.request,json,time
base='http://127.0.0.1:11434'
def call(path,body=None):
 return json.load(urllib.request.urlopen(urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'}),timeout=180))
call('/api/embed',{'model':'embeddinggemma:300m','input':[],'keep_alive':0})
opts={'num_thread':12,'num_gpu':25,'num_ctx':2048,'num_batch':512}
for texts in [['Validação sintética.']*16,['O prazo fictício é de sete dias úteis para a equipe Aurora. '*70]]:
 start=time.monotonic();r=call('/api/embed',{'model':'embeddinggemma:300m','input':texts,'truncate':False,'keep_alive':-1,'options':opts})
 print(json.dumps({'seconds':time.monotonic()-start,'dimensions':len(r['embeddings'][0]),'residency':call('/api/ps')}),flush=True)
PY
