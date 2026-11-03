"""Publish the user-supplied manifesto through the audited identity API."""
import pathlib,importlib.util,subprocess,json
root=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import json,sys,urllib.request
token=sys.stdin.readline().strip();body=json.loads(sys.stdin.read())
def call(path,body=None):
 request=urllib.request.Request('http://localhost:8075/api/v1/identity'+path,
  data=json.dumps(body).encode() if body is not None else None,
  headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=20) as r:return json.load(r)
active=call('')
from moara.identity import Identity
expected=Identity(body)
if active['sha256']==expected.sha256:
 print(json.dumps({'already_published':True,'version':active['version'],'sha256':active['sha256']}))
else:
 assert active['version']=='1.0.0','Unexpected active identity; do not overwrite concurrent publication'
 draft=call('/drafts',{'body':body})
 published=call('/drafts/'+draft['id']+'/publish',{'expected_active_id':active['publication']['id'],'expected_sha256':draft['sha256']})
 current=call('');assert current['sha256']==expected.sha256 and current['version']=='2.0.0'
 print(json.dumps({'version':current['version'],'sha256':current['sha256'],'publication_id':published['id'],
  'previous_publication_id':active['publication']['id'],'previous_sha256':active['sha256'],'history_preserved':True}))
'''
candidate=(root/'tmp/moara2-stage-name.txt').read_text().strip()
fixture=m.admin_session()+'\n'+(root/'moara/identity/manifest/identity.json').read_text()
process=subprocess.run(['docker','exec','-i',candidate,'python','-c',code],input=fixture,text=True,capture_output=True,timeout=60)
if process.returncode:raise RuntimeError(process.stderr[-1500:])
value=json.loads(process.stdout);(root/'docs/runtime/moara2-identity-publication-20261030.json').write_text(json.dumps(value,indent=2))
print(json.dumps(value))
