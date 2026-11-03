import pathlib,json,subprocess,shutil
root=pathlib.Path(__file__).resolve().parents[2]
image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
for name in ['unified-ui-public.json','ide-sdk-public.json']:
 report=json.loads((root/'docs/runtime'/name).read_text());assert report['checks'] and all(report['checks'].values())
 if name.startswith('unified-ui'):
  assert report['tested_image_id']==image
  artifacts=root/'infrastructure/site-entry'/('unified-output-'+report['test_container'].rsplit('-',1)[1])
  for file in ['rbac-user.png','rbac-admin.png']:shutil.copyfile(artifacts/file,root/'docs/runtime'/file)
 shutil.copyfile(root/'docs/runtime'/name,root/'docs/runtime'/('identity-rbac-public.json' if name.startswith('unified-ui') else 'identity-rbac-sdk.json'))
code=r'''
import asyncio,json,httpx,uuid
from moara.gateway.settings import Settings
from moara.gateway.database import Database
from moara.gateway.auth import Auth
from moara.gateway.rbac import PERMISSIONS,ROLES
async def main():
 s=Settings.load();d=Database(s)
 async with httpx.AsyncClient(timeout=20,trust_env=False) as c:
  a=Auth(s,d,c);row=await d.execute('SELECT * FROM moara.accounts WHERE id=CAST(:id AS uuid)',{'id':'99588b2b-df8d-4402-846f-92343a0e949f'},one=True)
  actor=await a.from_row(row);assert 'administrator' in actor.roles and all(actor.can(p) for p in PERMISSIONS)
  stored=await d.execute("SELECT permissions FROM moara.roles WHERE id='user'",one=True);assert set(stored['permissions'])==ROLES['user'][1]
  # Fixtures from this task only: never delete accounts, conversations or documents.
  fixtures=await d.execute("SELECT id FROM moara.accounts WHERE auth_source='local' AND email LIKE 'rbac-qa-%@example.invalid' AND name LIKE 'RBAC QA %'")
  for f in fixtures:
   await d.execute('UPDATE moara.accounts SET active=false WHERE id=CAST(:id AS uuid)',f)
   await d.execute('UPDATE moara.sessions SET revoked_at=now() WHERE account_id=CAST(:id AS uuid)',f)
   await d.execute('UPDATE moara.chats SET archived=true WHERE account_id=CAST(:id AS uuid)',f)
  r=await c.get(s.legacy_gateway+'/v1/inference/status',headers={'Authorization':'Bearer '+s.llm_key});r.raise_for_status();status=r.json();assert status['principal_resident']
  print(json.dumps({'owner_all_permissions':True,'stored_default_chat_only':True,'principal_resident':status['principal_resident'],'embeddings_resident':status.get('embeddings_resident'),'synthetic_accounts_disabled':len(fixtures)}))
  await a.close()
 await d.dispose()
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c',code],capture_output=True,text=True)
if r.returncode:raise RuntimeError('Final protected RBAC checks failed')
result=json.loads(r.stdout);stopped=[]
for name in subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines():
 if name.startswith(('moara-unified-stage-','moara-unified-proxy-stage-')):
  info=json.loads(subprocess.check_output(['docker','inspect',name]))[0];assert not info['HostConfig'].get('PortBindings')
  subprocess.run(['docker','stop',name],check=True,capture_output=True);stopped.append(name)
for filename in ['README.md','docs/PROJECT_STATUS.md','docs/MOARA_2_OPERATIONS.md']:
 path=root/filename;target=('docs/' if filename=='README.md' else '')+'MOARA_IDENTITY_RBAC_2026-10-31.md'
 if target not in path.read_text():
  with path.open('a') as out:out.write('\n\nIdentidade e acessos: [cadastro automatico, RBAC e administracao]('+target+').\n')
result.update(published=True,image=image,stopped_private_candidates=stopped)
(root/'docs/runtime/identity-rbac-final.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
