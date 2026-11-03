import pathlib,subprocess,json,importlib.util,sys
root=pathlib.Path(__file__).resolve().parents[2];stage='--stage' in sys.argv
cfg=json.loads((root/'tmp/public-web-stage.json').read_text()) if stage else {'core':'ai-server-moara-gateway-1','mcp':'ai-server-moara-legal-mcp-1'}
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import sys,json,httpx,re,base64,gzip,hashlib
from moara.gateway.settings import secret,Settings
data=json.load(sys.stdin);checks={};cases=[]
with httpx.Client(trust_env=False,timeout=240) as c:
 endpoint='http://'+data['mcp']+':8076/mcp'
 def tool(name,args):
  r=c.post(endpoint,headers={'Authorization':'Bearer '+secret('moara_legal_key'),'MCP-Protocol-Version':'2025-11-25'},json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':name,'arguments':args}})
  r.raise_for_status();return r.json()['result']['structuredContent']
 lookup=tool('search_web',{'query':'Angular signals documentacao oficial','urls':['https://angular.dev/guide/signals'],'max_results':1})
 checks['mcp_retrieves_real_public_page']=lookup['status']=='retrieved_content' and bool(lookup['sources'])
 assert checks['mcp_retrieves_real_public_page'],lookup['gaps']
 source=lookup['sources'][0]
 checks['snapshot_matches_hash']=hashlib.sha256(gzip.decompress(base64.b64decode(source['snapshot_gzip_base64']))).hexdigest()==source['sha256']
 checks['extraction_is_not_snippet']=source['text_characters']>500 and source['extractor']=='trafilatura-2.3.1'
 checks['official_text_is_not_certified_by_search']=lookup['legal_conclusion_allowed'] is False
 for question in ['Explique fotossintese de forma simples.','Ensine a preparar uma receita simples de bolo.','Pesquise na web a documentacao oficial do Angular Signals e explique como funcionam.','Qual a lei de cargos e salarios do judiciario federal?']:
  r=c.post('http://localhost:8075/api/v1/chat/completions',headers={'Authorization':'Bearer '+data['token']},json={'model':'auto','messages':[{'role':'user','content':question}],'max_tokens':800})
  r.raise_for_status();value=r.json();text=value['choices'][0]['message']['content'];metadata=value.get('moara',{})
  checks['no_purpose_gate_'+str(len(cases)+1)]=not re.search('qual.*finalidade institucional|qual.*finalidade funcional',text,re.I) and len(text)>70
  if 'Angular' in question:
   research=metadata.get('web_research',{})
   checks['chat_used_self_hosted_search']=research.get('provider')=='searxng_self_hosted' and research.get('status')=='retrieved_content'
   checks['chat_explains_web_content']=research.get('inference_used') is True and '[W' in text
   identifier=research['evidence_id'];e=c.get('http://localhost:8075/api/v1/web/evidence/'+identifier,headers={'Authorization':'Bearer '+data['token']});e.raise_for_status()
   record=e.json();checks['evidence_can_be_replayed']=record['kind']=='web_research' and record['rechecked_now'] is False and bool(record['retrieval']['sources'])
   checks['unauthenticated_evidence_is_denied']=c.get('http://localhost:8075/api/v1/web/evidence/'+identifier).status_code==401
  if 'cargos' in question:
   checks['legal_answer_keeps_official_sources']='11.416' in text or '11416' in text
   checks['legal_answer_has_legal_verification']='legal_verification' in metadata
  cases.append({'question':question,'answer':text,'metadata':metadata})
 print(json.dumps({'checks':checks,'cases':cases,'retrieval_source':{k:v for k,v in source.items() if k!='snapshot_gzip_base64'}},ensure_ascii=True))
'''
r=subprocess.run(['docker','exec','-i',cfg['core'],'python','-c',code],input=json.dumps({'token':m.admin_session(),'mcp':cfg['mcp']}),capture_output=True,text=True,timeout=1000)
if r.returncode:raise RuntimeError('Synthetic validation failed: '+r.stderr[-1300:])
report=json.loads(r.stdout);report['images']={name:subprocess.check_output(['docker','inspect',container,'--format','{{.Image}}'],text=True).strip() for name,container in cfg.items() if name in ('core','mcp')}
(root/'docs/runtime'/('public-web-live-stage.json' if stage else 'public-web-live-public.json')).write_text(json.dumps(report,indent=2))
print(json.dumps(report['checks']));assert all(report['checks'].values()),report['checks']
