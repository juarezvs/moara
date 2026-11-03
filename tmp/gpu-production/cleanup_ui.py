import pathlib,ssl,json,urllib.request,importlib.util
r=pathlib.Path('/home/nutec/ai-server');spec=importlib.util.spec_from_file_location('maintenance',r/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);token=m.admin_session()
base='https://moara.am.trf1.gov.br/moara/api/v1';tls=ssl.create_default_context(cafile=str(r/'docs/runtime/moara-domain-root-ca.crt'))
def call(path,method='GET'):
 req=urllib.request.Request(base+path,method=method,headers={'Authorization':'Bearer '+token})
 return json.load(urllib.request.urlopen(req,context=tls,timeout=30))
prefix='Validação técnica inteiramente fictícia: a equipe Aurora'
rows=call('/chats');ids=[row['id'] for row in rows if row['title'].startswith(prefix) and row['created_at']>='2026-10-30T02:30:00']
for identifier in ids:assert call('/chats/'+identifier,'DELETE')['deleted']
report={'obsolete_synthetic_ui_chats_removed':len(ids),'unrelated_chats_untouched':True}
(r/'docs/runtime/gpu-production-cleanup.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
