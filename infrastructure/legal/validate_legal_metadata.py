import pathlib,subprocess,json,importlib.util,sys
root=pathlib.Path(__file__).resolve().parents[2];public='--public' in sys.argv
core='ai-server-moara-gateway-1' if public else json.loads((root/'tmp/legal-metadata-stage.json').read_text())['core']
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import asyncio,json,sys,base64,gzip,hashlib,httpx
from pathlib import Path
from moara.gateway.settings import Settings
from moara.legal_mcp.lexml_catalog import parse_lexml,list_record
async def main():
 token=sys.stdin.read().strip();headers={'Authorization':'Bearer '+token};checks={}
 async with httpx.AsyncClient(trust_env=False,timeout=45) as c:
  url='http://localhost:8075/api/v1/legal/metadata'
  checks['authentication_required']=(await c.get(url)).status_code==401
  r=await c.get(url+'?limit=50',headers=headers);r.raise_for_status();first=r.json();items=first['items']
  for page in range(2,(first['total']+49)//50+1):
   r=await c.get(url+'?limit=50&page='+str(page),headers=headers);r.raise_for_status();v=r.json();assert v['version']==first['version'];items.extend(v['items'])
  checks['all_pages_accounted_for']=len(items)==first['total']==first['counts']['metadata_records']
  checks['no_duplicate_norms']=len({(r['norm']['kind'],r['norm']['number'],r['norm']['year']) for r in items})==len(items)
  r=await c.get(url,params={'query':'estatuto servidor'},headers=headers);r.raise_for_status();checks['alias_search_finds_law_8112']=any(i['norm']['number']==8112 for i in r.json()['items'])
  r=await c.get(url+'?number=14133&year=2021',headers=headers);r.raise_for_status();checks['exact_identity_filter']=len(r.json()['items'])==1 and r.json()['items'][0]['norm']['number']==14133
  r=await c.get(url,params={'query':'" OR 1=1 --'},headers=headers);r.raise_for_status();checks['untrusted_search_not_executed']=r.json()['total']==0
  r=await c.get(url+'/export',headers=headers);r.raise_for_status();out=r.json();checks['export_complete']=len(out['items'])==len(items);raws={}
  for s in out['snapshots']:
   raw=gzip.decompress(base64.b64decode(s['snapshot_gzip_base64']));assert hashlib.sha256(raw).hexdigest()==s['sha256'];raws[s['sha256']]=raw
  checks['all_archived_sources_pass_sha256']=bool(raws)
  for item in out['items']:
   source=item['catalogue_snapshot'];raw=raws[source['sha256']];data=json.loads(raw);wanted=item['norm']
   if 'ListaDocumento' in data:
    rows=data['ListaDocumento']['documentos']['documento'];rows=rows if isinstance(rows,list) else [rows];rows=[r for r in rows if int(str(r['numero']).replace('.',''))==wanted['number']]
   else:
    doc=data['DetalheDocumento']['documentos']['documento'][0];rows=[{**doc['identificacao'],'ementa':doc.get('ementa','')}]
   assert len(rows)==1
   expected=list_record(rows[0],wanted['kind'],source['url'],item['metadata_collected_at'])
   assert all(item[k]==expected[k] for k in expected)
   meta=item.get('lexml',{})
   if meta.get('snapshot'):
    actual=parse_lexml(raws[meta['snapshot']['sha256']].decode('utf8'),item['urn']);assert all(meta[k]==actual[k] for k in actual)
  checks['every_metadata_record_matches_official_snapshot']=True
  checks['metadata_not_misrepresented_as_normative_text']=first['normative_text'] is False and first['freshly_rechecked'] is False and first['legal_conclusion_allowed'] is False
  key=Path('/run/secrets/moara_legal_key').read_text().strip();s=Settings.load()
  r=await c.post(s.legal_mcp_url,headers={'Authorization':'Bearer '+key,'MCP-Protocol-Version':'2025-11-25'},json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'search_legal_metadata','arguments':{'number':8112,'year':1990}}});r.raise_for_status();v=r.json()['result']['structuredContent'];checks['mcp_tool_uses_same_catalogue']=v['version']==first['version'] and v['items'][0]['norm']['number']==8112 and v['normative_text'] is False
  print(json.dumps({'checks':checks,'total':first['total'],'counts':first['counts'],'version':first['version'],'collected_at':first['collected_at']},ensure_ascii=True));assert all(checks.values())
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i',core,'python','-c',code],input=m.admin_session(),capture_output=True,text=True,timeout=300)
if r.stdout:
 d=json.loads(r.stdout);d['tested_image_id']=subprocess.check_output(['docker','inspect',core,'--format','{{.Image}}'],text=True).strip();(root/'docs/runtime'/('legal-metadata-public.json' if public else 'legal-metadata-stage.json')).write_text(json.dumps(d,indent=2));print(json.dumps(d))
if r.returncode:raise RuntimeError('Metadata validation failed: '+r.stderr[-1000:])
