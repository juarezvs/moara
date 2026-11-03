import pathlib,json,subprocess
ROOT=pathlib.Path('/home/nutec/ai-server')
for filename in ['legal-information-public.json','legal-information-ui.json']:
 report=json.loads((ROOT/'docs/runtime'/filename).read_text());assert all(report['checks'].values())
for file in ['README.md','docs/PROJECT_STATUS.md','docs/MOARA_2_OPERATIONS.md']:
 path=ROOT/file;target=('docs/' if file=='README.md' else '')+'MOARA_LEGAL_INFORMATION_2026-10-30.md'
 if target not in path.read_text():
  with path.open('a') as out:out.write('\n\nConsultas informativas e limites de dispensa: [correcao, fontes e verificacoes]('+target+').\n')
stopped=[]
for name in subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines():
 if name.startswith(('moara-legal-information-stage-','moara-legal-app-information-stage-')):
  info=json.loads(subprocess.check_output(['docker','inspect',name]))[0];assert not info['HostConfig'].get('PortBindings')
  subprocess.run(['docker','stop',name],check=True,capture_output=True);stopped.append(name)
code="""import asyncio,json
import httpx
from moara.gateway.settings import Settings
async def main():
 s=Settings.load()
 async with httpx.AsyncClient(timeout=20,trust_env=False) as c:
  r=await c.get(s.legacy_gateway+'/v1/inference/status',headers={'Authorization':'Bearer '+s.llm_key});r.raise_for_status();data=r.json();assert data['principal_resident']
  print(json.dumps({'principal_resident':data['principal_resident'],'embeddings_resident':data.get('embeddings_resident')}))
asyncio.run(main())"""
r=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c',code],capture_output=True,text=True,check=True)
result=json.loads(r.stdout);result['published']=True;result['mcp_version']='0.3.0';result['preserved_stopped_candidates']=stopped
result['gateway_image']=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
(ROOT/'docs/runtime/legal-information-final.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
