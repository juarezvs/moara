"""Real model/API regression checks; keep bearer credentials only in stdin."""
import pathlib,subprocess,json,importlib.util,sys
root=pathlib.Path(__file__).resolve().parents[2];stage='--stage' in sys.argv
core=json.loads((root/'tmp/explanation-stage.json').read_text())['core'] if stage else 'ai-server-moara-gateway-1'
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import asyncio,json,sys,time,re,httpx
async def main():
 token=sys.stdin.read().strip();reports=[]
 cases=[('promotion','de acordo com a lei 8112/1990 o que é uma promoção?','grounded_explanation',['provimento','promoção']),('dialogue','me explique como funciona e os critérios para usar a modalidade diálogo competitivo.','grounded_explanation',['diálogo','contrata']),('identity','qual a lei de cargos e salários do judiciário federal?','official_identity_answer',['11','416']),('greeting','quais suas habilidades?',None,['Moara'])]
 async with httpx.AsyncClient(trust_env=False,timeout=300) as c:
  for name,query,status,keywords in cases:
   start=time.monotonic();r=await c.post('http://localhost:8075/v1/chat/completions',headers={'Authorization':'Bearer '+token},json={'model':'auto','messages':[{'role':'user','content':query}],'max_tokens':768});r.raise_for_status();v=r.json();answer=v['choices'][0]['message']['content'];meta=v['moara'].get('legal_verification',{})
   checks={'requested_behavior':meta.get('answer_status')==status if status else not meta,'topic_answered':all(k.casefold() in answer.casefold() for k in keywords),'not_sources_only':meta.get('answer_status')!='quoted_sources_fallback','official_citations':('[L' in answer and '](https://' in answer) if status else True}
   reports.append({'case':name,'question':query,'checks':checks,'answer':answer,'metadata':meta,'seconds':round(time.monotonic()-start,2)})
 print(json.dumps(reports,ensure_ascii=True))
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i',core,'python','-c',code],input=m.admin_session(),text=True,capture_output=True,timeout=1300)
if r.returncode:raise RuntimeError('Regression request failed: '+r.stderr[-1000:])
reports=json.loads(r.stdout);checks={item['case']+'_'+k:v for item in reports for k,v in item['checks'].items()}
data={'checks':checks,'reports':reports,'tested_image_id':subprocess.check_output(['docker','inspect',core,'--format','{{.Image}}'],text=True).strip()}
(root/'docs/runtime'/('explanation-regressions-stage.json' if stage else 'explanation-regressions-public.json')).write_text(json.dumps(data,indent=2,ensure_ascii=True))
print(json.dumps({'checks':checks,'seconds':[r['seconds'] for r in reports]}));assert all(checks.values())
