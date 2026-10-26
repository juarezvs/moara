"""Queue measured CPU matrices for installed candidates; never change old aliases."""
import importlib.util
import json
import ssl
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
token=module.admin_session();tls=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/ai-root-ca.crt'))
def call(path,body=None):
    request=urllib.request.Request('https://localhost:8443/moara/api/v1'+path,data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    with urllib.request.urlopen(request,context=tls,timeout=30) as response:return json.load(response)
models=call('/models');jobs=[]
for model in models:
    catalog_id=model['settings'].get('catalog_id')
    if catalog_id not in ['gemma4-12b','qwen25-coder-7b','qwen3-embedding-06b'] or not model['installed']:continue
    result=call('/admin/model-benchmarks',{'model_id':model['id'],'contexts':[4096,8192],'threads':[12,16],
        'idempotency_key':'reconstruction-cpu-matrix-v1-'+catalog_id})
    jobs.append({'catalog_id':catalog_id,**result});print(catalog_id,result['status'],flush=True)
(ROOT/'docs/runtime/moara-candidate-benchmarks.json').write_text(json.dumps(jobs,indent=2))
