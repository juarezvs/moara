"""Real official API checks through the authenticated private MCP."""
import sys,pathlib,json,subprocess
root=pathlib.Path(__file__).resolve().parents[2]
stage=json.loads((root/'tmp/legal-v2-stage.json').read_text())
public='--public' in sys.argv
core='ai-server-moara-gateway-1' if public else stage['core']
target='moara-legal-mcp' if public else stage['mcp']
code=r'''
import asyncio,json,base64,gzip,hashlib,time,sys
from pathlib import Path
import httpx
from moara.legal_mcp.contracts import today
target=sys.argv[1];checks={};reports=[];bundles=[]
async def main():
 async with httpx.AsyncClient(trust_env=False,timeout=85) as client:
  headers={'Authorization':'Bearer '+Path('/run/secrets/moara_legal_key').read_text().strip(),'MCP-Protocol-Version':'2025-11-25','Accept':'application/json, text/event-stream'}
  async def rpc(method,params):
   r=await client.post('http://'+target+':8076/mcp',headers=headers,json={'jsonrpc':'2.0','id':len(reports)+1,'method':method,'params':params});r.raise_for_status();return r.json()['result']
  init=await rpc('initialize',{});checks['version_02']=init['serverInfo']['version']=='0.2.0'
  tools=await rpc('tools/list',{});checks['three_tools']=len(tools['tools'])==3
  value=(await rpc('tools/call',{'name':'search_federal_norms','arguments':{'kind':'LEI','number':14133,'year':2021}}))['structuredContent']
  checks['real_senado_catalogue']=len(value.get('candidates',[]))==1 and value['candidates'][0]['number']==14133
  bundles.append(value)
  cases=[('cpc_before','LEI',13105,2015,'12','2015-12-31'),('cpc_after','LEI',13105,2015,'12','2020-01-01'),
    ('licitacoes_current','LEI',14133,2021,'6',str(today())),('adi_missing_text','LEI',9868,1999,'27',str(today())),
    ('emenda_constitucional','EMC',132,2023,'1',str(today()))]
  for label,kind,number,year,article,at in cases:
   start=time.monotonic()
   value=(await rpc('tools/call',{'name':'verify_legal_sources','arguments':{'reference_date':at,'norms':[{'kind':kind,'number':number,'year':year,'articles':[article]}]}}))['structuredContent']
   bundles.append(value)
   norm=value.get('norms',[{}])[0] if value.get('norms') else {}
   reports.append({'case':label,'seconds':round(time.monotonic()-start,2),'status':value['status'],'norm_status':norm.get('status'),
    'excerpt_count':len(norm.get('excerpts',[])),'version_dates':sorted(set(e['version_date'] for e in norm.get('excerpts',[]))),
    'snapshots':len(norm.get('snapshots',[])),'related_norms':len(norm.get('related_norm_verification',{}).get('checks',[])),
    'camara_status':norm.get('legislative_history',{}).get('status'),
    'source_results':[{'url':a['url'],'status':a['status'],'http_status':a.get('http_status')} for a in norm.get('source_checks',[])]})
   checks[label+'_blocked_unconfirmed_conclusions']=value.get('legal_conclusion_allowed') is False
   if label in ['cpc_before','cpc_after','licitacoes_current']:checks[label+'_official_text']=bool(norm.get('excerpts'))
   if label=='licitacoes_current':
    checks['automatic_camara_origin']=norm.get('legislative_history',{}).get('bill')=={'kind':'PL','number':6814,'year':2017}
    checks['automatic_camara_history']=norm.get('legislative_history',{}).get('status')=='legislative_history_retrieved'
    checks['amending_norm_publications_checked']=bool(norm.get('related_norm_verification',{}).get('checks'))
   if label=='adi_missing_text':checks['missing_text_not_fabricated']=not norm.get('excerpts') and norm.get('status')=='unconfirmed'
   if label=='emenda_constitucional':checks['constitutional_amendment_identity']=norm.get('source','').endswith('urn:lex:br:federal:emenda.constitucional:2023-12-20;132')
  before=bundles[1]['norms'][0]['excerpts'];after=bundles[2]['norms'][0]['excerpts']
  checks['historical_and_later_wording_differ']=[e['text'] for e in before]!=[e['text'] for e in after]
  checks['future_versions_not_used_in_past']=all(e['version_date']<='2015-12-31' for e in before)
  value=(await rpc('tools/call',{'name':'consult_legislative_history','arguments':{'bill':{'kind':'PL','number':6814,'year':2017},'reference_date':'2020-01-01'}}))['structuredContent']
  bundles.append(value);checks['real_camara_historical_lookup']=value['status']=='legislative_history_retrieved'
  checks['camara_is_not_normative_text']=value['normative_text'] is False
  checks['camara_events_respect_date']=all(e['dataHora'][:10]<='2020-01-01' for e in value['events'])
  all_snapshots=[]
  for package in bundles:
   all_snapshots.extend(package.get('snapshots',[]))
   for norm in package.get('norms',[]):all_snapshots.extend(norm.get('snapshots',[]))
  checks['all_snapshot_hashes_reproduce']=bool(all_snapshots) and all(hashlib.sha256(gzip.decompress(base64.b64decode(s['snapshot_gzip_base64']))).hexdigest()==s['sha256'] for s in all_snapshots)
  result={'checks':checks,'cases':reports,'snapshot_count':len(all_snapshots)}
  print(json.dumps(result),flush=True)
  assert all(checks.values())
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i',core,'python','-',target],input=code,text=True,capture_output=True,timeout=500)
name='legal-sources-v2-live-public.json' if public else 'legal-sources-v2-live-stage.json'
if r.stdout:
 data=json.loads(r.stdout.strip().splitlines()[-1]);data['tested_image_id']=subprocess.check_output(['docker','inspect',core,'--format','{{.Image}}'],text=True).strip();(root/'docs/runtime'/name).write_text(json.dumps(data,indent=2));print(json.dumps(data))
if r.returncode:print(r.stderr[:1500])
raise SystemExit(r.returncode)
