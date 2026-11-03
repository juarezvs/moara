import pathlib,subprocess,json,importlib.util,sys
root=pathlib.Path(__file__).resolve().parents[2];public='--public' in sys.argv
core='ai-server-moara-gateway-1' if public else json.loads((root/'tmp/stf-catalog-stage.json').read_text())['core']
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import asyncio,json,sys,base64,gzip,hashlib,httpx
from pathlib import Path
from moara.gateway.settings import Settings
from moara.legal_mcp.stf_catalog import decode_bank
async def main():
 token=sys.stdin.read().strip();headers={'Authorization':'Bearer '+token};checks={}
 async with httpx.AsyncClient(trust_env=False,timeout=30) as c:
  url='http://localhost:8075/api/v1/legal/stf-theses'
  r=await c.get(url);checks['authentication_required']=r.status_code==401
  r=await c.get(url+'?limit=50',headers=headers);r.raise_for_status();first=r.json();counts=first['counts'];items=first['items'];version=first['version']
  for page in range(2,(first['total']+49)//50+1):
   r=await c.get(url+'?limit=50&page='+str(page),headers=headers);r.raise_for_status();value=r.json();assert value['version']==version;items.extend(value['items'])
  checks['all_pages_match_complete_bank_counts']=len(items)==first['total']==sum(counts.values())
  checks['no_themes_lost_or_duplicated']=len({(r['theme'],r['bank']) for r in items})==len(items)
  for bank in ('com','sem'):
   r=await c.get(url+'?bank='+bank,headers=headers);r.raise_for_status();v=r.json();checks[bank+'_classification_preserved']=v['total']==counts[bank] and all(i['bank']==bank for i in v['items'])
  r=await c.get(url,params={'query':'ICMS PIS COFINS'},headers=headers);r.raise_for_status();v=r.json();checks['text_search_identifies_theme_69']=bool(v['items']) and v['items'][0]['theme']==69
  r=await c.get(url+'?theme=99999',headers=headers);r.raise_for_status();checks['absent_theme_not_invented']=r.json()['total']==0
  r=await c.get(url+'/export',headers=headers);r.raise_for_status();data=r.json();checks['export_has_all_records']=len(data['items'])==first['total'];expected=[]
  for snapshot in data['manifest']['snapshots']:
   raw=gzip.decompress(base64.b64decode(snapshot['snapshot_gzip_base64']));assert hashlib.sha256(raw).hexdigest()==snapshot['sha256']
   if snapshot['bank']:expected.extend(decode_bank(raw,snapshot['bank']))
  checks['every_record_matches_official_response_snapshot']=sorted(expected,key=lambda r:(r['theme'],r['bank'],r['record_sha256']))==data['items']
  checks['snapshot_not_misrepresented_as_new_legal_verification']=first['freshly_rechecked'] is False and first['legal_conclusion_allowed'] is False and 'pendente' in first['notice']
  s=Settings.load();key=Path('/run/secrets/moara_legal_key').read_text().strip()
  r=await c.post(s.legal_mcp_url,headers={'Authorization':'Bearer '+key,'MCP-Protocol-Version':'2025-11-25'},json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'search_stf_thesis_catalog','arguments':{'query':'ICMS PIS COFINS','bank':'com','limit':5}}});r.raise_for_status();v=r.json()['result']['structuredContent'];checks['mcp_catalogue_tool_available']=v['available'] and v['items'][0]['theme']==69 and v['freshly_rechecked'] is False
 print(json.dumps({'checks':checks,'counts':counts,'total':first['total'],'version':version,'collected_at':first['collected_at']},ensure_ascii=True));assert all(checks.values())
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i',core,'python','-c',code],input=m.admin_session(),capture_output=True,text=True,timeout=300)
if r.stdout:
 d=json.loads(r.stdout);d['tested_image_id']=subprocess.check_output(['docker','inspect',core,'--format','{{.Image}}'],text=True).strip();(root/'docs/runtime'/('stf-catalog-public.json' if public else 'stf-catalog-stage.json')).write_text(json.dumps(d,indent=2));print(json.dumps(d))
if r.returncode:raise RuntimeError('Catalogue validation failed: '+r.stderr[-1000:])
