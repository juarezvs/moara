"""Production acceptance with synthetic inputs; preserve/archive test content."""
import pathlib,importlib.util,subprocess,json
root=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import sys,json,time,urllib.request,urllib.error,base64,uuid,io,zipfile,concurrent.futures
token=sys.stdin.readline().strip();report={};document=None;keys=[]
def call(path,body=None,bearer=None,expected=200):
 request=urllib.request.Request('http://localhost:8075/api/v1'+path,
  data=json.dumps(body).encode() if body is not None else None,
  headers={'Authorization':'Bearer '+(bearer or token),'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(request,timeout=180) as response:status=response.status;raw=response.read()
 except urllib.error.HTTPError as error:status=error.code;raw=error.read()
 assert status==expected,{'path':path,'status':status}
 return json.loads(raw)
def chat(identifier,text,documents=None):
 start=time.monotonic();value=call('/chat/completions',{'model':'auto','assistant_id':identifier,'document_ids':documents or [],
  'messages':[{'role':'user','content':text}],'max_tokens':96,'temperature':0})
 return value,round(time.monotonic()-start,2)
try:
 identity=call('/identity');assert identity['version']=='2.0.0';report['identity_sha256']=identity['sha256']
 status=call('/observability/inference')
 assert status['available'] and status['transport']=='mutual_tls_over_ssh' and status['principal_resident'] and status['embeddings_resident'],status
 assert status['gpu']['available'] and status['queue']['concurrency']==1
 report['inference']=status
 catalog=call('/assistants');assert len(catalog)==6 and all(a['authorized'] and a['enabled'] for a in catalog)
 cases=[('juridica','Analise juridicamente a competência federal.'),
  ('gabinete','Explique um método para organizar a cronologia de autos, sem citar legislação.'),
  ('administrativa','Descreva uma estrutura de termo de referência para cadeiras, sem citar legislação.'),
  ('documental','Explique como comparar versões de documentos institucionais.'),
  ('desenvolvedora','Escreva uma função Python curta para normalizar códigos de unidades institucionais.'),
  ('dados','Explique uma metodologia de indicadores institucionais sem executar consultas.')]
 start=time.monotonic()
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  futures=[pool.submit(chat,*case) for case in cases]
  results=[]
  for (identifier,_),future in zip(cases,futures):
   value,elapsed=future.result();meta=value['moara'];assert meta['assistant']['id']==identifier
   if identifier=='juridica':assert meta['legal_verification']['status']=='clarification_required'
   else:assert meta.get('execution_backend')=='gpu' and meta.get('model_id')=='63af8a56-5676-52b1-b969-887658bb937d',{'assistant':identifier,'metadata':meta}
   results.append({'assistant':identifier,'seconds':elapsed,'backend':meta.get('execution_backend'),'passed':True})
 report['six_concurrent_requests']={'wall_seconds':round(time.monotonic()-start,2),'results':results,'serialized_inference':True}
 for identifier,text in [('auto','Escolha seis números para a loteria.'),('auto','Publique uma sentença automaticamente.')]:
  value,_=chat(identifier,text);assert value['moara']['policy']['decision']=='blocked'
 report['scope_and_official_acts_blocked']=True
 for text in ['Consulte os autos fictícios no PJe.','Consulte o processo fictício no SEI.']:
  value,_=chat('auto',text);assert value['moara']['policy']['reason']=='official_integration_pending_homologation' and not value['moara']['inference_used']
 report['PJe_SEI_prepared_and_disabled']=True
 value,elapsed=chat('juridica','CPC, art. 12; data de referência: 2020-01-01. Confira as fontes oficiais para este teste fictício.')
 legal=value['moara']['legal_verification'];assert legal['legal_conclusion_allowed'] is False
 evidence_id=legal.get('evidence_id')
 assert evidence_id,legal
 evidence=call('/legal/evidence/'+evidence_id);assert evidence
 report['legal_preflight']={'seconds':elapsed,'status':legal['status'],'evidence_id':evidence_id,'legal_conclusions_suspended':True}
 payload=io.BytesIO()
 with zipfile.ZipFile(payload,'w') as z:
  z.writestr('[Content_Types].xml','<Types/>')
  z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="PrazoFicticio" r:id="rId1"/></sheets></workbook>')
  z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/></Relationships>')
  z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="A1" t="inlineStr"><is><t>Prazo interno ficticio de revisao</t></is></c><c r="B1" t="inlineStr"><is><t>nove dias uteis</t></is></c></row></sheetData></worksheet>')
 document=call('/platform/documents',{'filename':'moara2-validacao-producao.xlsx','title':'Moara2 — planilha sintética de validação',
  'content_base64':base64.b64encode(payload.getvalue()).decode()},expected=201)
 me=call('/auth/me')
 key=call('/admin/api-keys',{'account_id':me['id'],'name':'Moara2 synthetic production restricted test','scopes':['chat.use'],
  'allowed_profiles':['general'],'allowed_sources':[],'rpm':60,'validity_days':1},expected=201);keys.append(key['id'])
 call('/platform/resources/'+document['id'],bearer=key['token'],expected=403)
 call('/observability/inference',bearer=key['token'],expected=403)
 call('/chat/completions',{'model':'general','assistant_id':'documental','document_ids':[document['id']],
  'messages':[{'role':'user','content':'Resuma este documento institucional.'}]},bearer=key['token'],expected=403)
 report['restricted_key_cannot_read_documents_or_metrics']=True
 queued=call('/platform/runs',{'operation':'document.ingest','resource_id':document['id'],'input':{},'idempotency_key':str(uuid.uuid4())},expected=202)
 for _ in range(90):
  run=call('/platform/runs/'+queued['id'])
  if run['status']=='completed':break
  if run['status']=='failed':raise AssertionError(run.get('error_code'))
  time.sleep(1)
 else:raise AssertionError('XLSX indexing timeout')
 value,elapsed=chat('documental','Qual é o prazo interno fictício de revisão indicado na planilha? Cite a fonte.',[document['id']])
 answer=value['choices'][0]['message']['content'];assert ('nove' in answer.lower() or '9' in answer) and '[D1]' in answer
 assert value['moara']['citation_validation']=='passed' and value['moara']['execution_backend']=='gpu'
 report['xlsx_ingestion_and_cited_answer']={'passed':True,'seconds':elapsed,'sources':value['moara']['document_sources']}
finally:
 for identifier in keys:call('/admin/api-keys/'+identifier+'/revoke',{})
 if document:call('/platform/resources/'+document['id']+'/archive',{'version':document['version']})
 report['test_keys_revoked_and_document_archived']=True
print(json.dumps(report))
'''
process=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session()+'\n',text=True,capture_output=True,timeout=500)
if process.returncode:raise RuntimeError(process.stderr[-2500:])
value=json.loads(process.stdout);(root/'docs/runtime/moara2-production-acceptance-20261030.json').write_text(json.dumps(value,indent=2))
print(json.dumps(value))
