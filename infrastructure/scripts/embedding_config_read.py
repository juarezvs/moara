import importlib.util,json,ssl,urllib.request
from pathlib import Path
ROOT=Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
token=module.admin_session();tls=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/moara-domain-root-ca.crt'))
req=urllib.request.Request('https://moara.am.trf1.gov.br/api/v1/retrieval/embedding',headers={'Authorization':'Bearer '+token})
with urllib.request.urlopen(req,context=tls,timeout=30) as response:cfg=json.load(response)
keys=['RAG_EMBEDDING_ENGINE','RAG_EMBEDDING_MODEL','RAG_EMBEDDING_BATCH_SIZE','ENABLE_ASYNC_EMBEDDING','RAG_EMBEDDING_CONCURRENT_REQUESTS']
print(json.dumps({k:cfg.get(k) for k in keys}))
