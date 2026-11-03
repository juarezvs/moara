import pathlib,importlib.util,json,ssl,urllib.request
root=pathlib.Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
request=urllib.request.Request('https://moara.am.trf1.gov.br/api/v1/retrieval/config',headers={'Authorization':'Bearer '+m.admin_session()})
with urllib.request.urlopen(request,context=ssl.create_default_context(cafile=str(root/'docs/runtime/moara-domain-root-ca.crt')),timeout=30) as response:value=json.load(response)
print(json.dumps(value.get('RAG_TEMPLATE')))
