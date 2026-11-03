set -eu
python3 - <<'PY'
import urllib.request,json
u='http://127.0.0.1:11434'
def call(path,body=None):
 return json.load(urllib.request.urlopen(urllib.request.Request(u+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'}),timeout=120))
call('/api/embed',{'model':'embeddinggemma:300m','input':[],'keep_alive':0})
call('/api/embed',{'model':'embeddinggemma:300m','input':['Verificação técnica sintética de inicialização.'],'keep_alive':-1,'options':{'num_gpu':-1}})
print(json.dumps(call('/api/ps')),flush=True)
PY
