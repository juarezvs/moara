"""Synthetic acceptance against the published Moara, without user documents."""
import sys,pathlib,json,ssl,time,urllib.request,urllib.error,importlib.util,uuid,base64,concurrent.futures
ROOT=pathlib.Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);token=m.admin_session()
base='https://localhost:8443/moara/api/v1'
tls=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/ai-root-ca.crt'))
report={'synthetic_only':True,'checks':{},'chat_samples':[]};doc=None
def call(path,body=None,auth=True):
 headers={'Content-Type':'application/json'}
 if auth:headers['Authorization']='Bearer '+token
 req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
 with urllib.request.urlopen(req,context=tls,timeout=240) as response:
  raw=response.read();return json.loads(raw) if 'json' in response.headers.get('Content-Type','') else raw
def sample(prompt,profile='auto'):
 body={'model':profile,'messages':[{'role':'user','content':prompt}],'stream':True,'temperature':0,'max_tokens':128,'stream_options':{'include_usage':True}}
 req=urllib.request.Request(base+'/chat/completions',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 start=time.monotonic();first=None;answer='';meta={};done=False;usage={}
 with urllib.request.urlopen(req,context=tls,timeout=240) as response:
  for raw in response:
   line=raw.decode().strip()
   if not line.startswith('data:'):continue
   value=line[5:].strip()
   if value=='[DONE]':done=True;break
   data=json.loads(value);meta.update(data.get('moara',{}));usage=data.get('usage') or usage
   for choice in data.get('choices',[]):
    content=choice.get('delta',{}).get('content','') or ''
    if content and first is None:first=time.monotonic()-start
    answer+=content
 result={'profile_requested':profile,'seconds':time.monotonic()-start,'ttft_seconds':first,'done':done,'moara':meta,'usage':usage,'answer':answer}
 print(json.dumps({'chat':{k:v for k,v in result.items() if k!='answer'}},ensure_ascii=False),flush=True)
 return result
def job(operation,resource=None,params=None):
 run=call('/platform/runs',{'operation':operation,'resource_id':resource,'input':params or {},'idempotency_key':'gpu-'+uuid.uuid4().hex})
 start=time.monotonic()
 while time.monotonic()-start<240:
  result=call('/platform/runs/'+run['id'])
  if result['status'] not in ('queued','running'):
   assert result['status']=='completed',(operation,result.get('error_code'))
   return result
  time.sleep(1)
 raise RuntimeError('Synthetic job timed out')
try:
 report['checks']['health']=call('/health')['status']=='ok'
 report['checks']['ready']=call('/ready')['status']=='ready'
 for profile in ['auto','fast','general']:
  report['chat_samples'].append(sample('Texto fictício: a equipe Alfa responde em cinco dias úteis. Informe somente o prazo.',profile))
 report['checks']['default_and_legacy_profiles_use_gpu']=all(s['done'] and s['moara'].get('execution_backend')=='gpu' and s['moara']['model_name']=='Gemma 4 12B' for s in report['chat_samples'])
 report['chat_samples'].append(sample('Escreva somente uma função Python soma(a,b) que retorna a soma, sem executar código.'))
 report['checks']['simple_software_uses_gpu']=report['chat_samples'][-1]['moara'].get('execution_backend')=='gpu' and 'def soma' in report['chat_samples'][-1]['answer']
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  concurrent=list(pool.map(lambda _:sample('Resuma em três tópicos o fluxo fictício: receber pedido, conferir os documentos e responder em cinco dias úteis.'),range(2)))
 report['concurrent']=concurrent
 report['checks']['concurrent_streams']=all(s['done'] and s['moara'].get('execution_backend')=='gpu' for s in concurrent)
 identity=call('/chat/completions',{'model':'auto','messages':[{'role':'user','content':'Quem é você?'}],'max_tokens':64})
 report['checks']['identity_preserved']=identity['moara'].get('inference_used') is False and 'moara' in identity['choices'][0]['message']['content'].lower()
 tools=[{'type':'function','function':{'name':'emit_status','description':'Teste sintético sem efeitos externos.', 'parameters':{'type':'object','properties':{'status':{'type':'string','enum':['ok']}},'required':['status']}}}]
 result=call('/chat/completions',{'model':'auto','messages':[{'role':'user','content':'Use a ferramenta emit_status com status ok. Não responda em texto.'}],'tools':tools,'max_tokens':128,'temperature':0})
 calls=result['choices'][0]['message'].get('tool_calls',[])
 report['checks']['native_tools_on_gpu']=result['moara'].get('execution_backend')=='gpu' and len(calls)==1 and calls[0]['function']['name']=='emit_status'
 result=call('/chat/completions',{'model':'qwen3-8b-cpu','messages':[{'role':'user','content':'Responda somente OK.'}],'max_tokens':16,'temperature':0})
 report['checks']['cpu_alternative_preserved']=result['moara']['model_name']=='Qwen3 8B' and result['moara'].get('execution_backend')=='cpu'
 text='Documento inteiramente fictício de validação GPU. A equipe Aurora responde em sete dias úteis. A responsável fictícia é Ana Exemplo.'
 doc=call('/platform/documents',{'filename':'validacao-gpu-ficticia.txt','title':'Validação técnica GPU — documento fictício','content_base64':base64.b64encode(text.encode()).decode()})
 ingest=job('document.ingest',doc['id']);report['checks']['document_ingested']=ingest['result']['chunks']>0
 search=call('/platform/knowledge/search',{'query':'Qual é o prazo da equipe Aurora?','document_ids':[doc['id']]})
 report['checks']['retrieval_matches_source']=bool(search['matches']) and all(row['document_id']==doc['id'] for row in search['matches'])
 answer=job('knowledge.answer',params={'query':'Qual é o prazo da equipe Aurora? Responda brevemente e cite a fonte.','document_ids':[doc['id']],'model':'auto'})
 value=answer['result'];report['knowledge_answer']=value
 report['checks']['answer_with_citation']=bool(value.get('citations')) and '[1]' in value['text'] and ('sete' in value['text'].lower() or '7' in value['text'])
 pdf=call('/platform/runs/'+answer['id']+'/export?format=pdf');report['checks']['pdf_export']=pdf.startswith(b'%PDF-')
except Exception as error:
 report['error']=type(error).__name__+': '+str(error)[:500]
finally:
 if doc is not None:
  try:report['synthetic_document_archived']=call('/platform/resources/'+doc['id']+'/archive',{'version':doc['version']}).get('archived')
  except Exception as e:report['archive_error']=type(e).__name__
 target=ROOT/'docs/runtime/gpu-production-acceptance.json';target.write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps({'checks':report['checks'],'error':report.get('error'),'synthetic_document_archived':report.get('synthetic_document_archived'),'file':str(target)},ensure_ascii=False),flush=True)
if report.get('error') or not all(report['checks'].values()):raise SystemExit(1)
