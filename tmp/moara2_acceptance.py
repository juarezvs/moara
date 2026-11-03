import pathlib,importlib.util,subprocess,json,sys
root=pathlib.Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
container=sys.argv[1] if len(sys.argv)>1 else (root/'tmp/moara2-stage-name.txt').read_text().strip()
code=r'''
import sys,json,time,urllib.request,urllib.error,base64,uuid
token=sys.stdin.readline().strip();report=[];keys=[];document=None
def call(path,body=None,method=None,bearer=None,accept='application/json',expected=200):
 headers={'Authorization':'Bearer '+(bearer or token),'Accept':accept}
 if body is not None:headers['Content-Type']='application/json'
 request=urllib.request.Request('http://localhost:8075/api/v1'+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers=headers)
 try:
  with urllib.request.urlopen(request,timeout=120) as response:status=response.status;raw=response.read()
 except urllib.error.HTTPError as error:status=error.code;raw=error.read()
 assert status==expected,{'path':path,'status':status}
 return json.loads(raw) if accept=='application/json' else raw.decode()
def chat(text,assistant='auto',documents=None,stream=False,**extra):
 body={'model':'auto','assistant_id':assistant,'document_ids':documents or [],'messages':[{'role':'user','content':text}],
       'max_tokens':256,'temperature':0,'stream':stream,**extra}
 start=time.monotonic();value=call('/chat/completions',body,accept='text/event-stream' if stream else 'application/json')
 return value,round(time.monotonic()-start,2)
try:
 catalog=call('/assistants');assert len(catalog)==6 and all(a['authorized'] for a in catalog)
 report.append({'test':'six_assistants_catalog','passed':True,'count':len(catalog)})
 cases=[('juridica','Analise juridicamente a competência federal.'),
  ('gabinete','Prepare um roteiro para organizar a cronologia de autos judiciais, sem inventar fatos.'),
  ('administrativa','Elabore uma estrutura curta de termo de referência para aquisição de cadeiras com campos pendentes, sem inventar requisitos.'),
  ('documental','Explique como comparar versões de documentos institucionais preservando a fonte.'),
  ('desenvolvedora','Desenvolva uma função Python pequena para normalizar códigos de unidades institucionais.'),
  ('dados','Explique uma metodologia de indicadores institucionais sem executar consultas e sem inventar números.')]
 for identifier,text in cases:
  value,elapsed=chat(text,identifier);meta=value['moara'];assert meta['assistant']['id']==identifier
  if identifier=='juridica':assert meta['legal_verification']['status']=='clarification_required'
  else:
   assert meta['execution_backend']=='gpu',meta
   from moara.legal_mcp.contracts import identify
   if identify(value['choices'][0]['message']['content']):assert meta.get('legal_verification'),meta
  report.append({'test':'assistant_'+identifier,'passed':True,'seconds':elapsed,'profile':meta['profile'],
    'backend':meta.get('execution_backend'),'model_id':meta['model_id'],'answer_excerpt':value['choices'][0]['message']['content'][:160]})
 for text in ['Crie uma receita de bolo.','Escolha seis números para a loteria.','Publique uma sentença automaticamente.']:
  value,elapsed=chat(text);assert value['moara']['policy']['decision']=='blocked',value['moara']
  report.append({'test':'scope_block','passed':True,'request':text,'seconds':elapsed})
 value,elapsed=chat('Explique a legislação sobre exploração de loterias.');assert value['moara']['reason']=='legal_verification'
 report.append({'test':'legal_lottery_allowed','passed':True,'seconds':elapsed})
 value,elapsed=chat('Elabore material curto de capacitação sobre discriminação no serviço público.');assert value['moara']['execution_backend']=='gpu'
 report.append({'test':'legitimate_training_allowed','passed':True,'seconds':elapsed})
 integrations=call('/official-integrations');assert {i['id'] for i in integrations}=={'sei','pje'} and all(not i['enabled'] for i in integrations)
 for system in ['sei','pje']:
  disabled=call('/official-integrations/'+system+'/read',{'operation':'search_process','query':'synthetic fixture'},expected=409)
  assert disabled['detail']['external_request_sent'] is False
 report.append({'test':'PJe_SEI_pending_homologation','passed':True})
 for text in ['Consulte o processo fictício no SEI.','Busque os autos fictícios no PJe.']:
  value,elapsed=chat(text)
  assert value['moara']['policy']['reason']=='official_integration_pending_homologation',value['moara']
  assert not value['moara']['inference_used']
 report.append({'test':'chat_cannot_claim_unhomologated_system_access','passed':True})
 me=call('/auth/me')
 key=call('/admin/api-keys',{'account_id':me['id'],'name':'Moara2 synthetic restricted acceptance','scopes':['chat.use'],
    'allowed_profiles':['general'],'allowed_sources':[],'rpm':60,'validity_days':1},expected=201)
 keys.append(key['id']);restricted=key['token']
 call('/assistants/admin/catalog',bearer=restricted,expected=403)
 blocked=call('/chat/completions',{'model':'general','assistant_id':'dados','messages':[{'role':'user','content':'Explique indicadores institucionais'}]},bearer=restricted,expected=403)
 report.append({'test':'restricted_key_cannot_manage_or_gain_assistant_permissions','passed':True})
 config=next(v for v in call('/assistants/admin/catalog') if v['id']=='documental')
 update={'expected_revision':config['revision'],'enabled':config['enabled'],'instructions':config['instructions'],'tools':config['tools']}
 published=call('/assistants/admin/documental',update,method='PUT')
 assert published['revision']==config['revision']+1
 call('/assistants/admin/documental',update,method='PUT',expected=409)
 history=call('/assistants/admin/documental/versions')
 assert len(history)>=2 and history[0]['sha256']==config['prompt_sha256']
 report.append({'test':'prompt_versioning_and_optimistic_concurrency','passed':True,'revision':published['revision'],'behavior_changed':False})
 raw='DOCUMENTO INTEIRAMENTE FICTÍCIO PARA HOMOLOGAÇÃO. A equipe Ipê responde em nove dias úteis. Não há pessoas ou processos reais. Nenhuma outra regra foi estabelecida.'
 document=call('/platform/documents',{'filename':'moara2-synthetic-acceptance.txt','title':'Moara2 — documento sintético de homologação',
  'content_base64':base64.b64encode(raw.encode()).decode()},expected=201)
 queued=call('/platform/runs',{'operation':'document.ingest','resource_id':document['id'],'input':{},'idempotency_key':str(uuid.uuid4())},expected=202)
 for _ in range(90):
  run=call('/platform/runs/'+queued['id'])
  if run['status']=='completed':break
  if run['status']=='failed':raise AssertionError(run.get('error_code'))
  time.sleep(1)
 else:raise AssertionError('document indexing timeout')
 value,elapsed=chat('Resuma o prazo informado no documento fictício, sem inferir dados adicionais.','documental',[document['id']])
 meta=value['moara'];assert meta['citation_validation']=='passed',meta
 answer=value['choices'][0]['message']['content'];assert ('nove' in answer.lower() or '9' in answer) and '[D1]' in answer
 assert meta['execution_backend']=='gpu'
 report.append({'test':'authorized_RAG_documentary_answer','passed':True,'seconds':elapsed,'document_id':document['id'],'sources':meta['document_sources']})
 value,elapsed=chat('Resuma o prazo informado no documento fictício.','documental',[document['id']],True)
 assert '[DONE]' in value and 'citation_validation' in value
 report.append({'test':'sourced_SSE_validated_before_release','passed':True,'seconds':elapsed})
 print(json.dumps(report,ensure_ascii=True),flush=True)
finally:
 for identifier in keys:
  try:call('/admin/api-keys/'+identifier+'/revoke',{},expected=200)
  except Exception:print('RESTRICTED_TEST_KEY_REVOCATION_FAILED',file=sys.stderr)
 if document:
  try:call('/platform/resources/'+document['id']+'/archive',{'version':document['version']});print('SYNTHETIC_DOCUMENT_ARCHIVED',file=sys.stderr)
  except Exception:print('SYNTHETIC_DOCUMENT_ARCHIVAL_FAILED',file=sys.stderr)
'''
process=subprocess.run(['docker','exec','-i',container,'python','-c',code],input=m.admin_session()+'\n',text=True,capture_output=True,timeout=500)
target=root/'docs/runtime/moara2-acceptance-20261030.json'
if process.returncode==0:target.write_text(process.stdout)
print(process.stdout,flush=True)
if process.returncode:print(process.stderr[-2300:],flush=True)
raise SystemExit(process.returncode)
