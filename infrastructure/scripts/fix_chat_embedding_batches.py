"""Atualiza o lote em memória; a persistência exige chat-feedback-compose.yml."""
import importlib.util,json,ssl,urllib.request
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
token=module.admin_session();tls=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/moara-domain-root-ca.crt'))
BASE='https://moara.am.trf1.gov.br/api/v1/retrieval'
def call(path,body=None):
 req=urllib.request.Request(BASE+path,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},data=None if body is None else json.dumps(body).encode())
 with urllib.request.urlopen(req,context=tls,timeout=90) as response:return json.load(response)
keys=['RAG_EMBEDDING_ENGINE','RAG_EMBEDDING_MODEL','RAG_EMBEDDING_BATCH_SIZE','ENABLE_ASYNC_EMBEDDING','RAG_EMBEDDING_CONCURRENT_REQUESTS']
before=call('/embedding')
assert before['RAG_EMBEDDING_ENGINE']=='openai' and before['openai_config']['url'].rstrip('/')=='http://gateway:8000/v1'
payload={k:before[k] for k in keys};payload.update(RAG_EMBEDDING_BATCH_SIZE=16,RAG_EMBEDDING_CONCURRENT_REQUESTS=1)
call('/embedding/update',payload);after=call('/embedding')
assert all(after[k]==payload[k] for k in keys)
assert all(before[k]==after[k] for k in ['openai_config','ollama_config','azure_openai_config'])
report={'at':datetime.now(timezone.utc).isoformat(),'before':{k:before[k] for k in keys},'after':{k:after[k] for k in keys},'provider_credentials_unchanged':True,'restarted_services':False}
dest=ROOT/'docs/runtime/embedding-batch-fix-20261027.json';dest.write_text(json.dumps(report,indent=2));dest.chmod(0o600)
print(json.dumps(report))
