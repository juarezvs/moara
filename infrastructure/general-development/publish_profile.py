"""Versioned developer instructions, preserving enabled state/tools and rollback."""
import pathlib,subprocess,importlib.util,json,os
root=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
token=m.admin_session()
def call(action,revision=None):
 code="""import json,sys,httpx
from moara.identity.development import INSTRUCTIONS
d=json.load(sys.stdin);headers={'Authorization':'Bearer '+d['token']}
with httpx.Client(trust_env=False,timeout=30) as c:
 rows=c.get('http://localhost:8075/api/v1/assistants/admin/catalog',headers=headers);rows.raise_for_status()
 row=next(r for r in rows.json() if r['id']=='desenvolvedora')
 if d['action']=='read':print(json.dumps(row))
 elif row['instructions']==INSTRUCTIONS:print(json.dumps({'already_current':True,'revision':row['revision']}))
 else:
  assert row['revision']==d['revision'],'Assistant changed concurrently'
  r=c.put('http://localhost:8075/api/v1/assistants/admin/desenvolvedora',headers=headers,json={'expected_revision':row['revision'],'enabled':row['enabled'],'tools':row['tools'],'instructions':INSTRUCTIONS});r.raise_for_status();print(r.text)
"""
 r=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=json.dumps({'token':token,'action':action,'revision':revision}),capture_output=True,text=True,timeout=50)
 if r.returncode:raise RuntimeError('Versioned profile update failed: '+r.stderr[-600:])
 return json.loads(r.stdout)
before=call('read');folder=root/'backups/general-development-20261102';folder.mkdir(exist_ok=True);folder.chmod(0o700)
path=folder/'assistant-before.json'
if not path.exists():path.write_text(json.dumps(before,indent=2));path.chmod(0o600)
updated=call('publish',before['revision'])
(root/'docs/runtime/general-development-profile.json').write_text(json.dumps(updated,indent=2));print(json.dumps({'developer_profile_published':True,'revision':updated['revision'],'permissions_changed':False}))
