"""Publish RBAC, explicitly grant only the verified institution owner, retain rollback."""
import pathlib,json,subprocess,importlib.util,time
root=pathlib.Path(__file__).resolve().parents[2];container='ai-server-moara-gateway-1'
owner='99588b2b-df8d-4402-846f-92343a0e949f'
image=subprocess.check_output(['docker','image','inspect','moara-core:identity-rbac-20261031','--format','{{.Id}}'],text=True).strip()
before_image=subprocess.check_output(['docker','image','inspect','moara-core:pre-identity-rbac-20261031','--format','{{.Id}}'],text=True).strip()
assert subprocess.check_output(['docker','inspect',container,'--format','{{.Image}}'],text=True).strip()==before_image
report=json.loads((root/'docs/runtime/unified-ui-stage.json').read_text());assert all(report['checks'].values()) and report['tested_image_id']==image
assert 'Ran 126 tests' in (root/'tmp/identity-rbac-build.log').read_text()
backup=root/'backups/identity-rbac-20261031';backup.mkdir(exist_ok=True);backup.chmod(0o700)
wrapper=root/'moara/infrastructure/scripts/compose.sh';before=wrapper.read_bytes();(backup/'compose-before').write_bytes(before)
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);token=m.admin_session()
snapshot=r'''
import sys,json,asyncio,httpx,time,hmac,hashlib
from moara.gateway.settings import Settings
from moara.gateway.database import Database
async def main():
 data=json.load(sys.stdin);s=Settings.load();d=Database(s);identifier=data['owner']
 async with httpx.AsyncClient(timeout=20,trust_env=False) as c:
  stamp=str(int(time.time()));sig=hmac.new(s.forward_key.encode(),(stamp+':'+identifier).encode(),hashlib.sha256).hexdigest()
  r=await c.get(s.legacy_webui+'/api/v1/moara/internal/identity/'+identifier,headers={'X-Moara-Timestamp':stamp,'X-Moara-Signature':sig});r.raise_for_status();i=r.json()
  assert i.get('institutional_verified') is True and i.get('enabled') is True and i.get('organization')=='SJAM' and i.get('username')=='am200401'
  r=await c.get(s.legacy_webui+'/api/v1/users/'+identifier,headers={'Authorization':'Bearer '+data['token']});r.raise_for_status();old_role=r.json()['role']
 roles=await d.execute('SELECT id,name,permissions,builtin FROM moara.roles')
 grants=await d.execute('SELECT account_id,role_id FROM moara.account_roles WHERE account_id=CAST(:id AS uuid)',{'id':identifier})
 print(json.dumps({'roles':roles,'owner_grants':grants,'upstream_owner_role':old_role},default=str));await d.dispose()
asyncio.run(main())
'''
def run_code(code,data):
 r=subprocess.run(['docker','exec','-i',container,'python','-c',code],input=json.dumps(data),text=True,capture_output=True)
 if r.returncode:raise RuntimeError('Protected RBAC operation failed; inspect server logs without credentials')
 return r.stdout
state=json.loads(run_code(snapshot,{'owner':owner,'token':token}));(backup/'permissions-before.json').write_text(json.dumps(state));(backup/'permissions-before.json').chmod(0o600)
(root/'moara/infrastructure/identity-rbac-compose.yml').write_text('services:\n  moara-gateway:\n    image: moara-core:identity-rbac-20261031\n')
def up():
 subprocess.run(['sh',str(wrapper),'config','--quiet'],cwd=root,check=True)
 subprocess.run(['sh',str(wrapper),'up','-d','--no-deps','moara-gateway'],cwd=root,check=True)
 for _ in range(40):
  r=subprocess.run(['docker','exec',container,'python','-c','import urllib.request;assert urllib.request.urlopen("http://localhost:8075/api/v1/ready",timeout=3).status==200'],capture_output=True)
  if not r.returncode:return
  time.sleep(1)
 raise RuntimeError('Gateway not ready')
apply=r'''
import sys,json,asyncio,httpx
from moara.gateway.settings import Settings
from moara.gateway.database import Database,as_json
from moara.gateway.rbac import ROLES
async def main():
 data=json.load(sys.stdin);s=Settings.load();d=Database(s)
 # Explicit owner authorization also enables the existing institutional AD administration.
 async with httpx.AsyncClient(timeout=20,trust_env=False) as c:
  r=await c.post(s.legacy_webui+'/api/v1/users/'+data['owner']+'/update',headers={'Authorization':'Bearer '+data['token']},json={'role':'admin'});r.raise_for_status()
 async with d.engine.begin() as conn:
  await d.execute('SELECT pg_advisory_xact_lock(42612554)',conn=conn)
  for key,(label,permissions) in ROLES.items():
   await d.execute('UPDATE moara.roles SET name=:name,permissions=CAST(:permissions AS jsonb) WHERE id=:id AND builtin',{'id':key,'name':label,'permissions':as_json(sorted(permissions))},conn=conn)
  await d.execute("INSERT INTO moara.account_roles(account_id,role_id) VALUES(CAST(:id AS uuid),'administrator') ON CONFLICT DO NOTHING",{'id':data['owner']},conn=conn)
  await d.audit(None,'rbac.initial_administrator.confirmed',data['owner'],conn=conn)
  await d.audit(None,'rbac.default.chat_only',conn=conn)
 await d.dispose();print(json.dumps({'owner_admin':True,'default_chat_only':True}))
asyncio.run(main())
'''
restore=r'''
import sys,json,asyncio,httpx
from moara.gateway.settings import Settings
from moara.gateway.database import Database,as_json
async def main():
 data=json.load(sys.stdin);s=Settings.load();d=Database(s)
 async with d.engine.begin() as conn:
  await d.execute('SELECT pg_advisory_xact_lock(42612554)',conn=conn)
  for r in data['state']['roles']:
   await d.execute('UPDATE moara.roles SET name=:name,permissions=CAST(:permissions AS jsonb) WHERE id=:id',{'id':r['id'],'name':r['name'],'permissions':as_json(r['permissions'])},conn=conn)
  await d.execute('DELETE FROM moara.account_roles WHERE account_id=CAST(:id AS uuid)',{'id':data['owner']},conn=conn)
  for r in data['state']['owner_grants']:
   await d.execute('INSERT INTO moara.account_roles(account_id,role_id) VALUES(CAST(:id AS uuid),:role)',{'id':data['owner'],'role':r['role_id']},conn=conn)
 async with httpx.AsyncClient(timeout=20,trust_env=False) as c:
  r=await c.post(s.legacy_webui+'/api/v1/users/'+data['owner']+'/update',headers={'Authorization':'Bearer '+data['token']},json={'role':data['state']['upstream_owner_role']});r.raise_for_status()
 await d.dispose()
asyncio.run(main())
'''
try:
 wrapper.write_text(before.decode().replace(' "$@"',' \\\n -f moara/infrastructure/identity-rbac-compose.yml "$@"'));wrapper.chmod(0o755);up()
 run_code(apply,{'owner':owner,'token':token})
except Exception:
 run_code(restore,{'owner':owner,'token':token,'state':state});wrapper.write_bytes(before);wrapper.chmod(0o755);up();raise
print(json.dumps({'published':True,'image':image,'owner_admin':True,'default_chat_only':True,'inference_restarted':False}))
