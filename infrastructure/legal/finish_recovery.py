import pathlib,subprocess,json,shutil
root=pathlib.Path(__file__).resolve().parents[2]
image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
for filename in ['legal-recovery-public.json','unified-ui-public.json','ide-sdk-public.json']:
 report=json.loads((root/'docs/runtime'/filename).read_text());assert report['checks'] and all(report['checks'].values())
 if filename!='ide-sdk-public.json':assert report['tested_image_id']==image
 if filename=='unified-ui-public.json':
  target=root/'docs/runtime/legal-recovery-ui-public.json';shutil.copyfile(root/'docs/runtime'/filename,target)
  artifact=root/'infrastructure/site-entry'/('unified-output-'+report['test_container'].rsplit('-',1)[1])/'legal-discovery-chat.png';shutil.copyfile(artifact,root/'docs/runtime/legal-recovery-chat.png')
 if filename=='ide-sdk-public.json':shutil.copyfile(root/'docs/runtime'/filename,root/'docs/runtime/legal-recovery-sdk.json')
code="""import asyncio,json,httpx
from moara.gateway.settings import Settings
async def main():
 s=Settings.load()
 async with httpx.AsyncClient(timeout=20,trust_env=False) as c:
  h=await c.get(s.legal_mcp_url.rsplit('/mcp',1)[0]+'/health');h.raise_for_status();assert h.json()['version']=='0.6.0'
  r=await c.get(s.legacy_gateway+'/v1/inference/status',headers={'Authorization':'Bearer '+s.llm_key});r.raise_for_status();d=r.json();assert d['principal_resident']
  print(json.dumps({'mcp_version':'0.6.0','principal_resident':d['principal_resident'],'embeddings_resident':d.get('embeddings_resident')}))
asyncio.run(main())"""
r=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c',code],capture_output=True,text=True,check=True);result=json.loads(r.stdout)
stopped=[]
for name in subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines():
 if name.startswith(('moara-legal-recovery-stage-','moara-legal-app-recovery-stage-','moara-unified-proxy-stage-')):
  info=json.loads(subprocess.check_output(['docker','inspect',name]))[0];assert not info['HostConfig'].get('PortBindings')
  subprocess.run(['docker','stop',name],check=True,capture_output=True);stopped.append(name)
for filename in ['README.md','docs/PROJECT_STATUS.md','docs/MOARA_2_OPERATIONS.md']:
 path=root/filename;target=('docs/' if filename=='README.md' else '')+'MOARA_LEGAL_RECOVERY_2026-10-31.md'
 if target not in path.read_text():
  with path.open('a') as out:out.write('\n\nPesquisa por assunto: [legislacao, fontes oficiais e evidencias]('+target+').\n')
result.update(published=True,image=image,preserved_stopped_candidates=stopped)
(root/'docs/runtime/legal-recovery-final.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
