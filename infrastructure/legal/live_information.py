import pathlib,subprocess,json,importlib.util,sys
ROOT=pathlib.Path('/home/nutec/ai-server');public='--public' in sys.argv
stage=json.loads((ROOT/'tmp/legal-information-stage.json').read_text());core='ai-server-moara-gateway-1' if public else stage['core']
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import asyncio,json,sys,time,base64,gzip,hashlib
import httpx
from moara.legal_mcp.contracts import today
async def main():
 token=sys.stdin.read().strip();checks={};start=time.monotonic()
 async with httpx.AsyncClient(trust_env=False,timeout=160) as client:
  headers={'Authorization':'Bearer '+token}
  question='me mostre o limite financeiro para dispensa de licitação previsto na lei 14133/2021.'
  r=await client.post('http://localhost:8075/v1/chat/completions',headers=headers,json={'model':'auto','messages':[{'role':'user','content':question}],'max_tokens':512})
  assert r.status_code==200,(r.status_code,r.text[:180]);payload=r.json();answer=payload['choices'][0]['message']['content'];meta=payload['moara']['legal_verification']
  checks['exact_question_answered_without_date_prompt']=meta['status']=='official_information_retrieved' and 'Você quer considerar' not in answer
  checks['both_current_official_amounts']=all(v in answer for v in ['130.984,20','65.492,11','12.807/2025'])
  checks['strictly_inferior_not_inclusive']= 'valores inferiores' in answer
  checks['current_date_disclosed']=str(today()) in answer and meta['reference_date']==str(today())
  checks['no_unchecked_legal_opinion']=meta['legal_conclusion_allowed'] is False and meta['inference_used'] is False
  identifier=meta['evidence_id'];r=await client.get('http://localhost:8075/api/v1/legal/evidence/'+identifier+'?download=true',headers=headers);assert r.status_code==200
  evidence=r.json();package=evidence['verification'];snapshots=package.get('snapshots',[])
  checks['three_live_official_sources']=len(snapshots)==3 and len({s['url'] for s in snapshots})==3
  checks['source_bytes_reproducible']=bool(snapshots) and all(hashlib.sha256(gzip.decompress(base64.b64decode(s['snapshot_gzip_base64']))).hexdigest()==s['sha256'] for s in snapshots)
  checks['evidence_integrity']=evidence['integrity']=='stored_manifest_verified'
  checks['date_assumption_audited']=package['reference_date_basis']=='current_date_assumed_for_information'
  r=await client.get('http://localhost:8075/api/v1/legal/evidence/'+identifier,headers={**headers,'Accept':'text/html'});checks['html_evidence_shows_table_and_hashes']='130.984,20' in r.text and 'SHA-256' in r.text
  r=await client.post('http://localhost:8075/v1/chat/completions',headers=headers,json={'model':'auto','messages':[{'role':'user','content':'Posso contratar no meu caso pela Lei 14133/2021?'}],'max_tokens':64});assert r.status_code==200
  case=r.json();checks['case_still_requests_missing_date']=case['moara']['legal_verification']['status']=='clarification_required'
  report={'checks':checks,'seconds':round(time.monotonic()-start,2),'answer':answer,'evidence_id':identifier,'checked_at':package.get('checked_at')}
  print(json.dumps(report,ensure_ascii=True));assert all(checks.values()),checks
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i',core,'python','-c',code],input=m.admin_session(),text=True,capture_output=True,timeout=400)
if r.stdout:
 data=json.loads(r.stdout.strip().splitlines()[-1]);(ROOT/'docs/runtime'/('legal-information-public.json' if public else 'legal-information-stage.json')).write_text(json.dumps(data,ensure_ascii=True,indent=2));print(json.dumps(data,ensure_ascii=True))
if r.returncode:print(r.stderr[-1400:].split('Call log:')[0])
raise SystemExit(r.returncode)
