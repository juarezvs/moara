import base64,io,json,time,uuid
from pathlib import Path
import httpx
from docx import Document
from pypdf import PdfReader
c=httpx.Client(base_url='http://127.0.0.1:8075/api/v1/',headers={'Origin':'https://localhost:8443'},timeout=45)
r=c.post('auth/login',json={'email':'admin@staging.invalid','password':Path('/run/secrets/admin_password').read_text()});r.raise_for_status()
c.headers['Cookie']='__Secure-moara_session='+r.cookies.get('__Secure-moara_session');c.headers['X-Moara-CSRF']=r.json()['csrf_token']
checks={}
def post(path,data):
 r=c.post('platform/'+path,json=data);r.raise_for_status();return r.json()
doc=Document();p=doc.add_paragraph();p.add_run('Responsável: ').bold=True;p.add_run('{{nome}}');doc.add_table(rows=1,cols=1).cell(0,0).text='Equipe: {{equipe}}'
out=io.BytesIO();doc.save(out)
source=post('documents',{'filename':'modelo.docx','title':'Modelo fictício formatado','content_base64':base64.b64encode(out.getvalue()).decode()})
template=post('resources',{'kind':'template','title':'Modelo formatado','body':{'document_id':source['id'],'variables':['nome','equipe'],'text':''}})
rendered=post('templates/'+template['id']+'/render',{'version':1,'fields':{'nome':'Pessoa Exemplo','equipe':'Alfa'}})
result=Document(io.BytesIO(base64.b64decode(rendered['docx_base64'])))
checks['formatted_docx_http']=result.paragraphs[0].runs[0].bold and result.tables[0].cell(0,0).text=='Equipe: Alfa'
checks['pdf_http']=len(PdfReader(io.BytesIO(base64.b64decode(rendered['pdf_base64']))).pages)>0
project=post('resources',{'kind':'project','title':'Git fictício','body':{'language':'python','files':{'main.py':'print(42)'}}})
r=c.get('platform/projects/'+project['id']+'/git.bundle');r.raise_for_status();checks['git_export_http']=r.content.startswith(b'# v2 git bundle') or r.content.startswith(b'# v3 git bundle')
flow=post('resources',{'kind':'workflow','title':'Fluxo de template formatado','body':{'steps':[{'type':'template.render','parameters':{'template_id':template['id'],'version':1,'fields':{'nome':'Pessoa Exemplo','equipe':'Alfa'}}}]}})
job=post('runs',{'operation':'workflow.run','resource_id':flow['id'],'input':{},'idempotency_key':str(uuid.uuid4())})
for _ in range(30):
 r=c.get('platform/runs/'+job['id']);r.raise_for_status();data=r.json()
 if data['status'] not in ('queued','running'):break
 time.sleep(1)
checks['formatted_docx_workflow']=data['status']=='completed' and 'Pessoa Exemplo' in data['result']['steps'][0]['result']['text']
checks['template_sources_tracked']=set(data['source_ids'])=={source['id'],template['id']}
r=c.post('platform/runs',json={'operation':'agent.run','input':{'agent_id':{},'query':'teste'}})
checks['invalid_agent_rejected']=r.status_code==422
assert all(checks.values()),json.dumps(checks)
print(json.dumps({'checks':checks,'synthetic_only':True}))
