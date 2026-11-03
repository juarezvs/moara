import pathlib,subprocess,json,importlib.util,sys
root=pathlib.Path(__file__).resolve().parents[2];stage='--stage' in sys.argv;baseline='--baseline' in sys.argv
core=json.loads((root/'tmp/explanation-stage.json').read_text())['core'] if stage else 'ai-server-moara-gateway-1'
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import asyncio,json,sys,time,re,base64,gzip,hashlib,httpx
async def main():
 token=sys.stdin.read().strip();query='me explique a diferen\u00e7a entre cess\u00e3o e requisi\u00e7\u00e3o de servidor.';start=time.monotonic()
 async with httpx.AsyncClient(trust_env=False,timeout=240) as c:
  r=await c.post('http://localhost:8075/v1/chat/completions',headers={'Authorization':'Bearer '+token},json={'model':'auto','messages':[{'role':'user','content':query}],'max_tokens':768});r.raise_for_status();v=r.json();answer=v['choices'][0]['message']['content'];meta=v['moara'].get('legal_verification',{});package={}
  if meta.get('evidence_id'):
   r=await c.get('http://localhost:8075/api/v1/legal/evidence/'+meta['evidence_id']+'?download=true',headers={'Authorization':'Bearer '+token});r.raise_for_status();package=r.json()['verification']
  records=package.get('norms',[]);proofs=[p for n in records for p in n.get('snapshots',[])]+package.get('discovery',{}).get('snapshots',[])+package.get('recovery',{}).get('snapshots',[])
  checks={'actual_explanation':meta.get('answer_status')=='grounded_explanation','comparison_understood':package.get('grounded_response',{}).get('task')=='compare','both_concepts_explained':all(w in answer.lower() for w in ['cess\u00e3o','requisi\u00e7\u00e3o']),'consent_difference_explained':bool(re.search(r'concord|anu\u00eancia|consent',answer,re.I)) and bool(re.search(r'irrecus|prerrogativa',answer,re.I)),'official_citations_adjacent':bool(re.search(r'\[L[0-9]+\.[0-9]+\]\(https://',answer)),'no_source_only_fallback':'Encontrei estes dispositivos oficiais' not in answer,'evidence_reproducible':bool(proofs) and all(hashlib.sha256(gzip.decompress(base64.b64decode(p['snapshot_gzip_base64']))).hexdigest()==p['sha256'] for p in proofs),'no_unfounded_vigency_certificate':meta.get('legal_conclusion_allowed') is False}
  checks['no_role_inversion']=not re.search(r'requisitante\s+(?:(?:pode|poder[a\u00e1])\s+)?indicar',answer,re.I)
  checks['current_regulatory_source']=any(n.get('norm',{}).get('number')==10835 for n in records)
  discovery=package.get('discovery',{})
  print(json.dumps({'checks':checks,'seconds':round(time.monotonic()-start,2),'answer':answer,'metadata':meta,'grounded_response':package.get('grounded_response'),'excerpts':[{'norm':n.get('norm'),'excerpts':n.get('excerpts')} for n in records], 'discovery':{k:v for k,v in discovery.items() if k!='snapshots'},'recovery_steps':package.get('recovery',{}).get('steps',[]),'norms':[{'norm':n.get('norm'),'source':n.get('source'),'status':n.get('status'),'gaps':n.get('gaps'),'source_checks':n.get('source_checks')} for n in records]},ensure_ascii=True))
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i',core,'python','-c',code],input=m.admin_session(),text=True,capture_output=True,timeout=600)
if r.returncode:raise RuntimeError('Application validation failed: '+r.stderr[-1200:])
d=json.loads(r.stdout);d['tested_image_id']=subprocess.check_output(['docker','inspect',core,'--format','{{.Image}}'],text=True).strip()
(root/'docs/runtime'/('explanation-baseline.json' if baseline else 'explanation-stage.json' if stage else 'explanation-public.json')).write_text(json.dumps(d,indent=2,ensure_ascii=True));print(json.dumps({'checks':d['checks'],'seconds':d['seconds']}))
if not baseline:assert all(d['checks'].values())
