import pathlib,subprocess,json,importlib.util,sys
root=pathlib.Path(__file__).resolve().parents[2];stage='--stage' in sys.argv
core=json.loads((root/'tmp/chat-reading-stage.json').read_text())['core'] if stage else 'ai-server-moara-gateway-1'
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import asyncio,json,sys,time,re,base64,gzip,hashlib,httpx
async def main():
 token=sys.stdin.read().strip();query='qual tema do stf que trata de remedio de alto custo e suas respectivas teses';start=time.monotonic()
 async with httpx.AsyncClient(trust_env=False,timeout=240) as c:
  r=await c.post('http://localhost:8075/v1/chat/completions',headers={'Authorization':'Bearer '+token},json={'model':'auto','messages':[{'role':'user','content':query}],'max_tokens':2048});r.raise_for_status();v=r.json();answer=v['choices'][0]['message']['content'];meta=v['moara'].get('legal_verification',{});package={}
  if meta.get('evidence_id'):
   r=await c.get('http://localhost:8075/api/v1/legal/evidence/'+meta['evidence_id']+'?download=true',headers={'Authorization':'Bearer '+token});r.raise_for_status();package=r.json()['verification']
  records=package.get('precedents',[]);found={r['reference']['number']:r for r in records};proofs=[p for n in records for p in n.get('snapshots',[])]
  fresh=[p for p in proofs if p.get('role')=='fresh_official_published_theses']
  assert set(found)=={6,1234},'The answer must prioritize the main theme and its explicit official related thesis'
  checks={'structured_thesis_response':meta.get('answer_status')=='official_theme_theses_answer','themes_6_and_1234_identified':6 in found and 1234 in found,'both_theses_rechecked_now':all(found.get(n,{}).get('published_thesis',{}).get('freshly_rechecked') for n in [6,1234]),'leading_cases_match_verified_metadata':all(r['published_thesis']['leading_case']==r['official_theme']['leading_case'] for r in records if r.get('published_thesis')),'cumulative_six_requirements_preserved':'cumulativamente' in answer and all('('+letter+')' in answer for letter in 'abcdef'),'headings_comparison_and_full_text_available':'## Comparação' in answer and '| Tema |' in answer and '<details>' in answer,'sources_beside_thesis_text':'[Tese no STF](https://portal.stf.jus.br/repercussaogeral/teses.asp)' in answer,'official_body_snapshots_reproducible':bool(fresh) and all(hashlib.sha256(gzip.decompress(base64.b64decode(p['snapshot_gzip_base64']))).hexdigest()==p['sha256'] for p in proofs),'no_general_certificate_of_applicability':meta.get('legal_conclusion_allowed') is False,'no_model_invention_of_thesis_text':package.get('grounded_response',{}).get('inference_used') is False}
  print(json.dumps({'checks':checks,'seconds':round(time.monotonic()-start,2),'answer':answer,'metadata':meta,'themes':[{'reference':r.get('reference'),'source':r.get('source'),'official_theme':r.get('official_theme'),'thesis_rechecked':r.get('published_thesis',{}).get('freshly_rechecked'),'gaps':r.get('gaps'),'source_checks':r.get('source_checks')} for r in records],'discovery':{k:v for k,v in package.get('precedent_discovery',{}).items() if k not in ('snapshots','web_search')}},ensure_ascii=True))
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i',core,'python','-c',code],input=m.admin_session(),text=True,capture_output=True,timeout=360)
if r.returncode:raise RuntimeError('Chat reading validation failed: '+r.stderr[-1200:])
d=json.loads(r.stdout);d['tested_image_id']=subprocess.check_output(['docker','inspect',core,'--format','{{.Image}}'],text=True).strip()
(root/'docs/runtime'/('chat-reading-stage.json' if stage else 'chat-reading-public.json')).write_text(json.dumps(d,indent=2,ensure_ascii=True));print(json.dumps({'checks':d['checks'],'seconds':d['seconds']}));assert all(d['checks'].values())
