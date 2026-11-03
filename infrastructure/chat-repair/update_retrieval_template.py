"""Preserve the original question when Open WebUI builds an attachment prompt."""
import pathlib,importlib.util,json,ssl,urllib.request,hashlib
root=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
tls=ssl.create_default_context(cafile=str(root/'docs/runtime/moara-domain-root-ca.crt'));token=m.admin_session()
def call(path,body=None):
 request=urllib.request.Request('https://moara.am.trf1.gov.br/api/v1/retrieval'+path,
    data=json.dumps(body).encode() if body is not None else None,
    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 with urllib.request.urlopen(request,context=tls,timeout=45) as response:return json.load(response)
before=call('/config');template=before['RAG_TEMPLATE']
backup=root/'backups/chat-intent-20261030/rag-template-before.json';backup.parent.mkdir(exist_ok=True)
if not backup.exists():backup.write_text(json.dumps({'RAG_TEMPLATE':template}));backup.chmod(0o600)
suffix='\n<moara_user_query>\n{{QUERY}}\n</moara_user_query>\n'
if '<moara_user_query>' not in template:
 assert '{{QUERY}}' not in template and '[query]' not in template,'Inspect a concurrently customized template before editing'
 call('/config/update',{'RAG_TEMPLATE':template.rstrip()+'\n'+suffix})
after=call('/config')
assert '<moara_user_query>' in after['RAG_TEMPLATE'] and '{{QUERY}}' in after['RAG_TEMPLATE']
assert {k:v for k,v in before.items() if k!='RAG_TEMPLATE'}=={k:v for k,v in after.items() if k!='RAG_TEMPLATE'},'Unrelated configuration changed'
report={'question_placeholder_restored':True,'other_settings_unchanged':True,
    'before_template_sha256':hashlib.sha256(json.loads(backup.read_text())['RAG_TEMPLATE'].encode()).hexdigest(),
    'after_template_sha256':hashlib.sha256(after['RAG_TEMPLATE'].encode()).hexdigest()}
(root/'docs/runtime/chat-repair-retrieval-template.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
