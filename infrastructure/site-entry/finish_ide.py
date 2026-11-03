import pathlib,subprocess,json
ROOT=pathlib.Path('/home/nutec/ai-server')
for file in ['README.md','docs/PROJECT_STATUS.md','docs/MOARA_2_OPERATIONS.md']:
 path=ROOT/file;target=('docs/' if file=='README.md' else '')+'MOARA_VSCODE_API_2026-10-30.md'
 text=path.read_text()
 if 'MOARA_VSCODE_API_2026-10-30.md' not in text:
  with path.open('a') as out:out.write('\n\nAPI pessoal para VS Code: [acesso, configuracao e validacao]('+target+').\n')
reports={name:json.loads((ROOT/'docs/runtime'/name).read_text()) for name in ['ide-sdk-stage.json','ide-sdk-public.json','ide-ui.json']}
assert all(all(r['checks'].values()) for r in reports.values())
containers=json.loads(subprocess.check_output(['docker','ps','-a','--format','json'],text=True).strip().replace('\n',',' ).join(['[',']']))
stopped=[]
for row in containers:
 name=row['Names']
 if name.startswith('moara-ide-stage-'):
  info=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
  assert not info['HostConfig'].get('PortBindings')
  assert 'MOARA_BACKGROUND_JOBS=false' in info['Config']['Env']
  subprocess.run(['docker','stop',name],check=True,capture_output=True);stopped.append(name)
code="""import asyncio,json
import httpx
from moara.gateway.settings import Settings
from moara.gateway.database import Database
async def main():
 s=Settings.load();db=Database(s)
 row=await db.execute(\"SELECT count(*) AS active FROM moara.api_keys WHERE (name='IDE acceptance synthetic' OR name LIKE 'IDE browser synthetic%') AND revoked_at IS NULL\",one=True)
 assert row['active']==0
 await db.dispose()
 async with httpx.AsyncClient(timeout=20,trust_env=False) as c:
  r=await c.get(s.legacy_gateway+'/v1/inference/status',headers={'Authorization':'Bearer '+s.llm_key});r.raise_for_status();data=r.json()
  assert data['principal_resident']
  print(json.dumps({'synthetic_keys_revoked':True,'principal_resident':data['principal_resident'],'embeddings_resident':data.get('embeddings_resident')}))
asyncio.run(main())"""
run=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c',code],text=True,capture_output=True,check=True)
state=json.loads(run.stdout);state['preserved_stopped_candidates']=stopped
state['gateway_image']=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
state['published']=True
(ROOT/'docs/runtime/ide-final.json').write_text(json.dumps(state,indent=2))
print(json.dumps(state))
