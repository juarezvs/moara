import asyncio,base64,json,os,time,uuid
from pathlib import Path
import httpx
from moara.gateway import bootstrap
from moara.gateway.database import Database
from moara.gateway.settings import Settings
from moara.gateway.auth import Auth
async def seed():
 db=Database(Settings.load());p=Path('/tmp/synthetic-platform-model.json')
 p.write_text(json.dumps({'accounts':[],'groups':[],'group_members':[],'models':[{'id':'fast','name':'Local inference QA','is_active':True}],
 'grants':[{'resource_id':'fast','permission':'read','principal_type':'anyone','principal_id':'*'}],
 'physical_models':[{'alias':'fast','provider':'fixture','tag':'test-only','details':{'context_length':8192},'declared_capabilities':['completion'],'size_bytes':0,'digest':'synthetic-alias-to-existing-local-fast'}]}))
 os.environ['MOARA_BOOTSTRAP_CATALOG']=str(p)
 async with httpx.AsyncClient() as http:
  auth=Auth(Settings.load(),db,http)
  await bootstrap.seed(db,auth);await auth.close()
 await db.dispose();p.unlink()
asyncio.run(seed());checks={}
c=httpx.Client(base_url='http://127.0.0.1:8075/api/v1/',headers={'Origin':'https://localhost:8443'},timeout=30)
r=c.post('auth/login',json={'email':'admin@staging.invalid','password':Path('/run/secrets/admin_password').read_text()});r.raise_for_status()
c.headers['Cookie']='__Secure-moara_session='+r.cookies.get('__Secure-moara_session');c.headers['X-Moara-CSRF']=r.json()['csrf_token']
def call(path,body):
 r=c.post('platform/'+path,json=body);r.raise_for_status();return r.json()
def job(operation,resource=None,params=None):
 r=call('runs',{'operation':operation,'resource_id':resource,'input':params or {},'idempotency_key':str(uuid.uuid4())});start=time.monotonic()
 while time.monotonic()-start<500:
  response=c.get('platform/runs/'+r['id']);response.raise_for_status();data=response.json()
  if data['status'] not in ('queued','running'):
   if data['status']!='completed':raise AssertionError(operation+':'+str(data['error_code']))
   return data
  time.sleep(2)
 raise AssertionError('timeout_'+operation)
doc=call('documents',{'filename':'ficticio.txt','title':'Procedimento fictício Alfa','content_base64':base64.b64encode('Procedimento inteiramente fictício Alfa. O prazo para resposta da equipe Alfa é de cinco dias úteis. A responsável fictícia é Ana Exemplo.'.encode()).decode()})
result=job('document.ingest',doc['id']);checks['actual_local_embeddings']=result['result']['chunks']>0
result=job('knowledge.answer',params={'query':'Qual é o prazo de resposta da equipe Alfa? Cite a fonte.','document_ids':[doc['id']],'model':'fast'})
checks['actual_local_answer_with_citation']=bool(result['result']['citations']) and '[1]' in result['result']['text'] and ('cinco' in result['result']['text'].lower() or '5' in result['result']['text'])
checks['citation_source_matches']=result['result']['citations'][0]['document_id']==doc['id']
case=call('resources',{'kind':'case','title':'Processo inteiramente fictício','body':{'document_ids':[doc['id']],'description':'Exercício sem efeitos jurídicos','events':[]}})
legal=job('legal.draft',case['id'],{'query':'Resuma o prazo documentado em uma minuta curta.','model':'fast'})
checks['legal_draft_marked']=legal['result']['text'].startswith('RASCUNHO') and legal['result']['requires_review']
project=call('resources',{'kind':'project','title':'Projeto fictício mínimo','body':{'description':'Apenas main.py que imprime 42. Não adicione dependências.','language':'python','files':{}}})
proposal=job('project.generate',project['id'],{'instructions':'Gere somente main.py que imprime 42.','model':'fast'})
checks['developer_and_security_review']=proposal['result']['agent_steps']==['developer','security_reviewer'] and bool(proposal['result']['files'])
checks['generated_code_not_executed']=proposal['result']['executed'] is False
assert all(checks.values()),json.dumps(checks)
print('LOCAL_INFERENCE_REPORT='+json.dumps({'checks':checks,'synthetic_only':True,'production_records_created':False}))
