"""Record public verification and stop only isolated candidates."""
import pathlib,json,subprocess,shutil
ROOT=pathlib.Path('/home/nutec/ai-server')
image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
for filename in ['unified-ui-public.json','unified-routes-public.json','ide-sdk-public.json']:
 report=json.loads((ROOT/'docs/runtime'/filename).read_text())
 assert report['checks'] and all(report['checks'].values()),filename
 if filename.startswith('unified-ui'):assert report['tested_image_id']==image
shutil.copyfile(ROOT/'docs/runtime/ide-sdk-public.json',ROOT/'docs/runtime/unified-ide-sdk-public.json')
code="""import asyncio,json,httpx
from moara.gateway.settings import Settings
async def main():
 s=Settings.load()
 async with httpx.AsyncClient(timeout=20,trust_env=False) as c:
  r=await c.get(s.legacy_gateway+'/v1/inference/status',headers={'Authorization':'Bearer '+s.llm_key});r.raise_for_status();d=r.json();assert d['principal_resident']
  print(json.dumps({'principal_resident':d['principal_resident'],'embeddings_resident':d.get('embeddings_resident')}))
asyncio.run(main())"""
result=json.loads(subprocess.check_output(['docker','exec','ai-server-moara-gateway-1','python','-c',code],text=True))
stopped=[]
for name in subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines():
 if name.startswith(('moara-unified-stage-','moara-unified-proxy-stage-')):
  info=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
  assert not info['HostConfig'].get('PortBindings')
  subprocess.run(['docker','stop',name],check=True,capture_output=True);stopped.append(name)
for file in ['README.md','docs/PROJECT_STATUS.md','docs/MOARA_2_OPERATIONS.md']:
 path=ROOT/file;target=('docs/' if file=='README.md' else '')+'MOARA_UNIFIED_INTERFACE_2026-10-31.md'
 if target not in path.read_text():
  with path.open('a') as out:out.write('\n\nInterface unica: [contexto, identidade e historico]('+target+').\n')
result.update(published=True,gateway_image=image,preserved_stopped_candidates=stopped)
(ROOT/'docs/runtime/unified-final.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
