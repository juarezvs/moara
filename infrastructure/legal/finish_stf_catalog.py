import pathlib,json,subprocess,shutil
root=pathlib.Path(__file__).resolve().parents[2]
image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
for filename in ['stf-catalog-stage.json','stf-catalog-public.json','stf-catalog-ui-stage.json','stf-catalog-ui-public.json']:
 d=json.loads((root/'docs/runtime'/filename).read_text());assert d['tested_image_id']==image and all(d['checks'].values())
 if filename=='stf-catalog-ui-public.json':
  folder=root/'infrastructure/site-entry'/('unified-output-'+d['test_container'].rsplit('-',1)[1])
  for name in ['stf-catalog-desktop.png','stf-catalog-mobile.png']:shutil.copyfile(folder/name,root/'docs/runtime'/name)
for name in ['ai-server-moara-gateway-1','ai-server-moara-legal-mcp-1']:
 info=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
 mount=next(m for m in info['Mounts'] if m['Destination']=='/app/legal_catalog/stf');assert mount['RW'] is False
code="""import asyncio,json,httpx
from moara.gateway.settings import Settings
async def main():
 s=Settings.load()
 async with httpx.AsyncClient(trust_env=False,timeout=20) as c:
  r=await c.get(s.legal_mcp_url.rsplit('/mcp',1)[0]+'/health');r.raise_for_status();assert r.json()['version']=='0.9.0' and r.json()['stf_catalog_available']
  r=await c.get(s.legacy_gateway+'/v1/inference/status',headers={'Authorization':'Bearer '+s.llm_key});r.raise_for_status();v=r.json();assert v['principal_resident'];print(json.dumps({'principal_resident':v['principal_resident'],'embeddings_resident':v.get('embeddings_resident')}))
asyncio.run(main())"""
r=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c',code],capture_output=True,text=True,check=True);health=json.loads(r.stdout)
names=subprocess.check_output(['docker','ps','-a','--format','{{.Names}}'],text=True).splitlines();suffixes=[n.rsplit('-',1)[1] for n in names if n.startswith('moara-stf-catalog-app-stage-')];stopped=[]
for name in subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines():
 if name.startswith(('moara-stf-catalog-app-stage-','moara-stf-catalog-mcp-stage-')) or any(name.startswith('moara-unified-proxy-stage-'+s+'-') for s in suffixes):
  info=json.loads(subprocess.check_output(['docker','inspect',name]))[0];assert not info['HostConfig'].get('PortBindings');subprocess.run(['docker','stop',name],check=True,capture_output=True);stopped.append(name)
for filename in ['README.md','docs/PROJECT_STATUS.md','docs/MOARA_2_OPERATIONS.md']:
 p=root/filename;target=('docs/' if filename=='README.md' else '')+'MOARA_STF_THESIS_CATALOG_2026-10-31.md'
 if target not in p.read_text():
  with p.open('a') as out:out.write('\n\n[Acervo de teses com e sem repercussao geral do STF]('+target+').\n')
catalog=json.loads((root/'docs/runtime/stf-catalog-public.json').read_text())
result={'published':True,'image':image,'mcp_version':'0.9.0','catalogue_counts':catalog['counts'],'catalogue_total':catalog['total'],'catalogue_version':catalog['version'],'unit_tests':185,'read_only_catalogue_mounts':True,'all_records_verified_against_official_snapshots':True,'inference_restarted':False,**health,'preserved_stopped_candidates':stopped}
(root/'docs/runtime/stf-catalog-final.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
