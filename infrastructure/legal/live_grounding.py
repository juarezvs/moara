import pathlib,subprocess,json,importlib.util,sys
ROOT=pathlib.Path('/home/nutec/ai-server');public='--public' in sys.argv
stage=json.loads((ROOT/'tmp/legal-grounding-stage.json').read_text());core='ai-server-moara-gateway-1' if public else stage['core']
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import asyncio,json,sys,time,base64,gzip,hashlib
import httpx
from moara.legal_mcp.contracts import today
async def main():
 token=sys.stdin.read().strip();checks={};cases=[]
 async with httpx.AsyncClient(trust_env=False,timeout=180) as client:
  headers={'Authorization':'Bearer '+token}
  for label,question in [('promotion','de acordo com a lei 8112/1990 o que é uma promoção.'),('cpc','O que diz o art. 12 do CPC?'),('stj','Explique o Tema 1157 do STJ.')]:
   start=time.monotonic();r=await client.post('http://localhost:8075/v1/chat/completions',headers=headers,json={'model':'auto','messages':[{'role':'user','content':question}],'max_tokens':1024});assert r.status_code==200,(label,r.status_code,r.text[:100])
   data=r.json();answer=data['choices'][0]['message']['content'];meta=data['moara'].get('legal_verification',{})
   r=await client.get('http://localhost:8075/api/v1/legal/evidence/'+meta['evidence_id']+'?download=true',headers=headers);assert r.status_code==200
   evidence=r.json();package=evidence['verification'];records=package.get('norms',[])+package.get('precedents',[])
   snapshots=[s for rec in records for s in rec.get('snapshots',[])]
   checks[label+'_sources_retrieved']=meta['status']=='official_sources_retrieved'
   checks[label+'_grounded_explanation']=meta.get('answer_status')=='grounded_explanation'
   checks[label+'_sources_reproducible']=bool(snapshots) and all(hashlib.sha256(gzip.decompress(base64.b64decode(s['snapshot_gzip_base64']))).hexdigest()==s['sha256'] for s in snapshots)
   checks[label+'_no_blanket_block']='A análise conclusiva foi suspensa' not in answer and 'Serviço de conferência indisponível' not in answer
   checks[label+'_no_false_vigency_certificate']=meta.get('legal_conclusion_allowed') is False
   if label=='promotion':
    checks['promotion_devices_retrieved']=all(any(e['device']=='art'+a for rec in records for e in rec.get('excerpts',[])) for a in ['8','10','17'])
    checks['promotion_content_substantive']=all(t in answer.casefold() for t in ['provimento','carreira'])
    checks['promotion_gpu']=meta.get('execution_backend')=='gpu'
   cases.append({'label':label,'seconds':round(time.monotonic()-start,2),'meta':meta,'answer':answer,'sources':[{'status':rec.get('status'),'total':rec.get('retrieved_excerpt_count'),'excerpts':[e['device'] for e in rec.get('excerpts',[])],'gaps':rec.get('gaps',[])} for rec in records]})
  print(json.dumps({'checks':checks,'cases':cases},ensure_ascii=True));assert all(checks.values()),checks
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i',core,'python','-c',code],input=m.admin_session(),text=True,capture_output=True,timeout=600)
if r.stdout:
 data=json.loads(r.stdout.strip().splitlines()[-1]);data['tested_image_id']=subprocess.check_output(['docker','inspect',core,'--format','{{.Image}}'],text=True).strip();(ROOT/'docs/runtime'/('legal-grounding-public.json' if public else 'legal-grounding-stage.json')).write_text(json.dumps(data,ensure_ascii=True,indent=2));print(json.dumps(data,ensure_ascii=True))
if r.returncode:print(r.stderr[-1300:].split('Call log:')[0])
raise SystemExit(r.returncode)
