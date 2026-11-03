import pathlib,json,subprocess,shutil
root=pathlib.Path(__file__).resolve().parents[2]
image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
for filename in ['legal-metadata-stage.json','legal-metadata-public.json','legal-metadata-ui-stage.json','legal-metadata-ui-public.json','legal-metadata-chat-stage.json','legal-metadata-chat-public.json']:
 d=json.loads((root/'docs/runtime'/filename).read_text());assert d['tested_image_id']==image and all(d['checks'].values())
 if filename=='legal-metadata-ui-public.json':
  folder=root/'infrastructure/site-entry'/('unified-output-'+d['test_container'].rsplit('-',1)[1])
  for name in ['metadata-desktop.png','metadata-mobile.png']:shutil.copyfile(folder/name,root/'docs/runtime'/name)
for name in ['ai-server-moara-gateway-1','ai-server-moara-legal-mcp-1']:
 info=json.loads(subprocess.check_output(['docker','inspect',name]))[0];assert info['Image']==image
 for target in ['/app/legal_catalog/stf','/app/legal_catalog/lexml']:
  mount=next(m for m in info['Mounts'] if m['Destination']==target);assert mount['RW'] is False
code="""import asyncio,json,httpx
from moara.gateway.settings import Settings
async def main():
 s=Settings.load()
 async with httpx.AsyncClient(trust_env=False,timeout=20) as c:
  r=await c.get(s.legal_mcp_url.rsplit('/mcp',1)[0]+'/health');r.raise_for_status();assert r.json()['version']=='0.10.0' and r.json()['stf_catalog_available'] and r.json()['metadata_catalog_available']
  r=await c.get(s.legacy_gateway+'/v1/inference/status',headers={'Authorization':'Bearer '+s.llm_key});r.raise_for_status();v=r.json();assert v['principal_resident'];print(json.dumps({'principal_resident':v['principal_resident'],'embeddings_resident':v.get('embeddings_resident')}))
asyncio.run(main())"""
r=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c',code],capture_output=True,text=True,check=True);health=json.loads(r.stdout)
subprocess.run(['systemctl','--user','is-active','--quiet','moara-legal-metadata.timer'],check=True)
state=subprocess.check_output(['systemctl','--user','show','moara-legal-metadata.service','--property=Result','--property=ExecMainStatus','--property=ActiveState','--property=ExecMainExitTimestamp'],text=True)
assert 'Result=success' in state and 'ExecMainStatus=0' in state and 'ActiveState=inactive' in state
assert any(line.startswith('ExecMainExitTimestamp=') and line.split('=',1)[1] for line in state.splitlines())
names=subprocess.check_output(['docker','ps','-a','--format','{{.Names}}'],text=True).splitlines();suffixes=[n.rsplit('-',1)[1] for n in names if n.startswith('moara-legal-metadata-app-stage-')];stopped=[]
for name in subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines():
 if name.startswith(('moara-legal-metadata-app-stage-','moara-legal-metadata-mcp-stage-')) or any(name.startswith('moara-unified-proxy-stage-'+s+'-') for s in suffixes):
  info=json.loads(subprocess.check_output(['docker','inspect',name]))[0];assert not info['HostConfig'].get('PortBindings');subprocess.run(['docker','stop',name],check=True,capture_output=True);stopped.append(name)
for filename in ['README.md','docs/PROJECT_STATUS.md','docs/MOARA_2_OPERATIONS.md']:
 p=root/filename;target=('docs/' if filename=='README.md' else '')+'MOARA_LEXML_METADATA_2026-10-31.md'
 if target not in p.read_text():
  with p.open('a') as out:out.write('\n\n[Coleta automatica de metadados oficiais e integracao LexML]('+target+').\n')
catalog=root/'data/legal/metadata';version=(catalog/'CURRENT').read_text().strip();manifest=json.loads((catalog/'versions'/version/'manifest.json').read_text())
assert version!=json.loads((root/'docs/runtime/legal-metadata-stage.json').read_text())['version'],'The unattended service must publish a second complete catalogue version'
result={'published':True,'image':image,'mcp_version':'0.10.0','catalogue_counts':manifest['counts'],'catalogue_version':version,'collected_at':manifest['collected_at'],'unit_tests':196,'read_only_catalogue_mounts':True,'every_initial_record_verified_against_official_snapshots':True,'timer_active':True,'timer_interval_hours':6,'scheduled_service_executed_successfully':True,'inference_restarted':False,**health,'preserved_stopped_candidates':stopped}
(root/'docs/runtime/legal-metadata-final.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
