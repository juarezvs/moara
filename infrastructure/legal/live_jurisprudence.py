import pathlib,subprocess,json,importlib.util,sys
root=pathlib.Path(__file__).resolve().parents[2];public='--public' in sys.argv
stage=json.loads((root/'tmp/jurisprudence-stage.json').read_text());core='ai-server-moara-gateway-1' if public else stage['core']
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import asyncio,json,sys,time,gzip,base64,hashlib
import httpx
from moara.legal_mcp.contracts import today
async def main():
 token=sys.stdin.read().strip();checks={};cases=[]
 questions=[('hiv','qual o tema do stf que trata de pessoas que tem HIV tem direito a aposentadoria?',1310),('icms','qual o tema do STF sobre ICMS na base de cálculo do PIS e COFINS?',69),('dialogue','me explique como funciona e os critérios para usar a modalidade diálogo competitivo.',14133),('traffic','qual a lei que trata de crime de trânsitos?',9503),('privacy','Qual lei trata da proteção de dados pessoais?',13709),('domestic','Qual lei trata de violência doméstica contra a mulher?',11340),('promotion','de acordo com a lei 8112/1990 o que é uma promoção.',8112)]
 async with httpx.AsyncClient(trust_env=False,timeout=240) as c:
  for label,question,number in questions:
   start=time.monotonic();r=await c.post('http://localhost:8075/v1/chat/completions',headers={'Authorization':'Bearer '+token},json={'model':'auto','messages':[{'role':'user','content':question}],'max_tokens':1024})
   assert r.status_code==200,(label,r.status_code)
   data=r.json();answer=data['choices'][0]['message']['content'];meta=data['moara'].get('legal_verification',{})
   checks[label+'_does_not_ask_law_number']=bool(meta.get('evidence_id')) and meta.get('status')!='clarification_required'
   package={}
   if meta.get('evidence_id'):
    r=await c.get('http://localhost:8075/api/v1/legal/evidence/'+meta['evidence_id']+'?download=true',headers={'Authorization':'Bearer '+token});assert r.status_code==200
    package=r.json()['verification']
   records=package.get('norms',[])+package.get('precedents',[]);snapshots=[s for rec in records for s in rec.get('snapshots',[])]+package.get('discovery',{}).get('snapshots',[])+package.get('precedent_discovery',{}).get('snapshots',[])
   checks[label+'_correct_official_norm']=any((rec.get('norm') or rec.get('reference',{})).get('number')==number and rec.get('excerpts') for rec in records)
   checks[label+'_grounded_answer']=meta.get('answer_status')==('official_theme_answer' if label in ('hiv','icms') else 'official_conditions_answer' if label=='dialogue' else 'grounded_explanation' if label=='promotion' else 'official_identity_answer')
   if label=='promotion':
    from moara.gateway.legal_answer import sources
    literal=sources(package)[:4]
    literal_valid=bool(literal) and all(row['text'] in answer and row['source'] in answer for row in literal)
    checks[label+'_grounded_answer']=checks[label+'_grounded_answer'] or (meta.get('answer_status')=='quoted_sources_fallback' and literal_valid)
    checks['promotion_answer_uses_verified_sources']=checks[label+'_grounded_answer']
   checks[label+'_evidence_reproducible']=bool(snapshots) and all(hashlib.sha256(gzip.decompress(base64.b64decode(s['snapshot_gzip_base64']))).hexdigest()==s['sha256'] for s in snapshots)
   checks[label+'_no_false_certificate']=meta.get('legal_conclusion_allowed') is False
   if label not in ('promotion','dialogue','hiv','icms'):checks[label+'_official_subject_discovery']=bool(package.get('discovery',{}).get('candidates'))
   if label=='hiv':
    record=next((r for r in records if r.get('reference',{}).get('number')==1310),{})
    theme=record.get('official_theme',{})
    checks['hiv_leading_case_verified']='1447945' in theme.get('leading_case','').replace('.','')
    checks['hiv_military_scope_explicit']='reforma militar' in answer.casefold() and 'INSS' in answer
    checks['hiv_no_invented_final_thesis']=theme.get('final_merits_thesis_confirmed') is False
    checks['hiv_movements_checked']=theme.get('movements_checked') is True
   if label=='dialogue':
    checks['dialogue_recovery_attempted']=package.get('recovery',{}).get('attempted') is True
    checks['dialogue_article32_retrieved']=any(e['device'].startswith('art32') for r in records for e in r.get('excerpts',[]))
    checks['dialogue_criteria_explained']=any(t in answer.casefold() for t in ['inova','adapta','especifica'])
   cases.append({'label':label,'question':question,'seconds':round(time.monotonic()-start,2),'meta':meta,'answer':answer,'recovery':{k:v for k,v in package.get('recovery',{}).items() if k not in ('snapshots','initial_attempt','web_search')},'discovery':{k:v for k,v in package.get('discovery',{}).items() if k!='snapshots'},'norms':[{'norm':r.get('norm'),'status':r.get('status'),'devices':[e['device'] for e in r.get('excerpts',[])],'gaps':r.get('gaps',[])} for r in records]})
 print(json.dumps({'checks':checks,'cases':cases},ensure_ascii=True));assert checks and all(checks.values()),checks
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i',core,'python','-c',code],input=m.admin_session(),text=True,capture_output=True,timeout=1100)
if r.stdout:
 data=json.loads(r.stdout.strip().splitlines()[-1]);data['tested_image_id']=subprocess.check_output(['docker','inspect',core,'--format','{{.Image}}'],text=True).strip()
 (root/'docs/runtime'/('jurisprudence-public.json' if public else 'jurisprudence-stage.json')).write_text(json.dumps(data,ensure_ascii=True,indent=2));print(json.dumps({'checks':data['checks']}))
if r.returncode:print(r.stderr[-900:].split('Call log:')[0])
raise SystemExit(r.returncode)
