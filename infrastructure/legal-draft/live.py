import pathlib,subprocess,json,importlib.util,sys
root=pathlib.Path(__file__).resolve().parents[2];stage='--stage' in sys.argv
cfg=json.loads((root/'tmp/legal-draft-stage.json').read_text()) if stage else {'core':'ai-server-moara-gateway-1','mcp':'ai-server-moara-legal-mcp-1'}
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import sys,json,httpx,time,re
from moara.gateway.legal_drafting import PORTAL_DRAFT
data=json.load(sys.stdin);checks={};question='crie uma peti\u00e7\u00e3o para aposentadoria de um pescador, segurado especial, com fundamenta\u00e7\u00e3o jur\u00eddica robusta.'+'\n\n'+PORTAL_DRAFT
with httpx.Client(trust_env=False,timeout=600) as c:
 start=time.monotonic()
 r=c.post('http://localhost:8075/api/v1/chat/completions',headers={'Authorization':'Bearer '+data['token']},json={'model':'auto','messages':[{'role':'user','content':question}],'max_tokens':2800});r.raise_for_status();value=r.json()
 elapsed=time.monotonic()-start;text=value['choices'][0]['message']['content'];meta=value['moara']['legal_verification']
 checks['exact_request_delivers_petition']='PETI\u00c7\u00c3O INICIAL' in text and 'Dos pedidos' in text
 checks['does_not_ask_generic_date_or_subject']='informe a data relevante' not in text and 'Voc\u00ea quer considerar a data atual' not in text
 checks['pending_fields_not_invented_facts']=all(t in text for t in ['[DER','[PER\u00cdODOS]','[NOME DO REQUERENTE]','Hip\u00f3tese'])
 checks['draft_research_is_not_case_date']=meta['reference_date_basis']=='current_date_for_draft_research_not_case' and meta['draft'] is True
 checks['no_automatic_entitlement_claim']='voc\u00ea tem direito' not in text.casefold() and meta['legal_conclusion_allowed'] is False
 e=c.get('http://localhost:8075/api/v1/legal/evidence/'+meta['evidence_id'],headers={'Authorization':'Bearer '+data['token'],'Accept':'application/json'});e.raise_for_status();record=e.json();package=record['verification'];ground=package['grounded_response']
 checks['actual_official_8213_text_retrieved']=any(n.get('norm',{}).get('number')==8213 and n.get('excerpts') and n.get('snapshots') for n in package.get('norms',[]))
 checks['grounded_legal_reasoning_not_quote_fallback']=ground.get('status')=='grounded_explanation' and len({p['text'] for p in ground.get('points',[])})>=3
 checks['legal_claims_have_existing_source_ids']=bool(ground.get('source_ids')) and all('['+sid+'](' in text for sid in ground['source_ids'])
 checks['evidence_integrity_replayed']=record['integrity']=='stored_manifest_verified' and record['rechecked_now'] is False
 checks['date_and_private_fact_policy_recorded']=package['draft']['case_facts_confirmed'] is False and package['draft']['current_research_is_not_case_date'] is True
 from moara.gateway.legal_drafting import scope_issues
 checks['family_economy_is_not_universal_requirement']=not scope_issues([{'text':p['text']} for p in ground.get('points',[])],package)
 report={'checks':checks,'elapsed_seconds':round(elapsed,2),'question':question,'answer':text,'metadata':meta,'grounding_status':ground.get('status'),'validation_rejections':ground.get('validation_rejections'),'review_issues':ground.get('review_issues'),'failure_reason':ground.get('failure_reason'),'model_outputs':ground.get('model_outputs'),'sources':[{'norm':n.get('norm'),'source':n.get('source'),'devices':[e['device'] for e in n.get('excerpts',[])]} for n in package.get('norms',[])]}
 print(json.dumps(report,ensure_ascii=True))
'''
r=subprocess.run(['docker','exec','-i',cfg['core'],'python','-c',code],input=json.dumps({'token':m.admin_session()}),capture_output=True,text=True,timeout=900)
if r.returncode:raise RuntimeError('Draft validation failed: '+r.stderr[-1500:])
report=json.loads(r.stdout);report['images']={k:subprocess.check_output(['docker','inspect',cfg[k],'--format','{{.Image}}'],text=True).strip() for k in ['core','mcp']}
(root/('docs/runtime/legal-draft-live-stage.json' if stage else 'docs/runtime/legal-draft-live-public.json')).write_text(json.dumps(report,indent=2))
if not stage:(root/'docs/runtime/legal-draft-example.md').write_text(report['answer'])
print(json.dumps({'checks':report['checks'],'elapsed_seconds':report['elapsed_seconds'],'grounding_status':report['grounding_status'],'failure_reason':report.get('failure_reason')}));assert all(report['checks'].values())
