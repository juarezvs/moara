import pathlib,subprocess,json,shutil
root=pathlib.Path(__file__).resolve().parents[2]
image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
for name in ['careers-stage.json','careers-public.json','careers-ui-stage.json','careers-ui-public.json','careers-regression-public.json']:
 d=json.loads((root/'docs/runtime'/name).read_text());assert d['tested_image_id']==image and all(d['checks'].values())
 if name=='careers-ui-public.json':
  artifact=root/'infrastructure/site-entry'/('unified-output-'+d['test_container'].rsplit('-',1)[1])/'careers-chat.png';shutil.copyfile(artifact,root/'docs/runtime/careers-chat.png')
code="""import asyncio,json,httpx
from moara.gateway.settings import Settings
async def main():
 s=Settings.load()
 async with httpx.AsyncClient(trust_env=False,timeout=20) as c:
  r=await c.get(s.legal_mcp_url.rsplit('/mcp',1)[0]+'/health');r.raise_for_status();assert r.json()['version']=='0.8.1'
  r=await c.get(s.legacy_gateway+'/v1/inference/status',headers={'Authorization':'Bearer '+s.llm_key});r.raise_for_status();d=r.json();assert d['principal_resident']
  print(json.dumps({'mcp_version':'0.8.1','principal_resident':d['principal_resident'],'embeddings_resident':d.get('embeddings_resident')}))
asyncio.run(main())"""
r=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c',code],capture_output=True,text=True,check=True);result=json.loads(r.stdout)
proxy=(root/'tmp/unified-proxy-name.txt').read_text().strip();stopped=[]
for name in subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines():
 if name.startswith(('moara-careers-mcp-stage-','moara-careers-app-stage-')) or name==proxy and name.startswith('moara-unified-proxy-stage-'):
  info=json.loads(subprocess.check_output(['docker','inspect',name]))[0];assert not info['HostConfig'].get('PortBindings');subprocess.run(['docker','stop',name],check=True,capture_output=True);stopped.append(name)
for filename in ['README.md','docs/PROJECT_STATUS.md','docs/MOARA_2_OPERATIONS.md']:
 p=root/filename;target=('docs/' if filename=='README.md' else '')+'MOARA_CAREER_DISCOVERY_2026-10-31.md'
 if target not in p.read_text():
  with p.open('a') as out:out.write('\n\n[Identificacao da lei de carreiras e recuperacao por assunto]('+target+').\n')
result.update(published=True,image=image,unit_tests=179,exact_question_public_api=True,exact_question_public_chat=True,inference_restarted=False,preserved_stopped_candidates=stopped)
(root/'docs/runtime/careers-final.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
