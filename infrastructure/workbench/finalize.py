"""Metadata checks and cleanup of private UI candidates; keep all data/images."""
import pathlib,json,subprocess,importlib.util
root=pathlib.Path(__file__).resolve().parents[2]
report=json.loads((root/'docs/runtime/workbench-ui.json').read_text())
assert report.get('candidate_proxy') is False and all(report['checks'].values())
assert report.get('native_test_session_revoked') is True
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import sys,json,urllib.request
token=sys.stdin.read().strip()
def read(path):
 request=urllib.request.Request('http://localhost:8075/api/v1'+path,headers={'Authorization':'Bearer '+token})
 with urllib.request.urlopen(request,timeout=15) as response:return json.load(response)
status=read('/observability/inference');assert status['available'] and status['principal_resident'] and status['embeddings_resident']
assert status['transport']=='mutual_tls_over_ssh'
identity=read('/identity');assert identity['version']=='2.0.0'
print(json.dumps({'inference':status,'identity_sha256':identity['sha256']}))
'''
process=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session(),text=True,capture_output=True,timeout=45)
if process.returncode:raise RuntimeError(process.stderr[-1200:])
state=json.loads(process.stdout)
rows=[json.loads(line) for line in subprocess.check_output(['docker','ps','--format','json'],text=True).splitlines()]
candidates=[row['Names'] for row in rows if row['Names'].startswith('moara-workbench-stage-')]
if candidates:subprocess.run(['docker','stop',*candidates],check=True,stdout=subprocess.DEVNULL)
rows=[json.loads(line) for line in subprocess.check_output(['sh',str(root/'moara/infrastructure/scripts/compose.sh'),'ps','--format','json'],cwd=root,text=True).splitlines()]
assert all(row['State']=='running' and row.get('Health')!='unhealthy' for row in rows)
core=json.loads(subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1']))[0]
assert core['Config']['Image']=='moara-core:workbench-20261030'
state.update(image=core['Config']['Image'],image_id=core['Image'],services_running=len(rows),private_candidates_stopped=candidates,
    public_browser_checks=sum(type(value) is bool and value for value in report['checks'].values()),
    test_data_archived=report['checks']['synthetic_content_archived'])
(root/'docs/runtime/workbench-final-operation.json').write_text(json.dumps(state,indent=2))
print(json.dumps(state))
