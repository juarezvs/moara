"""Publish the tested application and gracefully reload only the upload proxy route."""
import pathlib,json,subprocess,time
root=pathlib.Path(__file__).resolve().parents[2];wrapper=root/'moara/infrastructure/scripts/compose.sh';caddy=root/'infrastructure/caddy/Caddyfile'
def output(args):return subprocess.check_output(args,text=True).strip()
tests=json.loads((root/'tmp/document-upload-tests.json').read_text());assert tests['passed'] and tests['tests']>=312
for name,field in [('document-upload-ui-stage.json','tested_image_id'),('document-upload-live-stage.json','image')]:
 report=json.loads((root/'docs/runtime'/name).read_text());assert all(report['checks'].values()) and report[field]==tests['image']
assert output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'])==output(['docker','image','inspect','moara-core:pre-document-upload-20261102','--format','{{.Id}}'])
assert json.loads((root/'docs/runtime/moara-preservation-latest.json').read_text())['verified'] is True
assert json.loads((root/'docs/runtime/document-upload-migration.json').read_text())['version']=='0011_streamed_documents'
assert caddy.read_bytes()==(root/'tmp/document-upload-caddy-before').read_bytes(),'Proxy changed since staging'
backup=root/'backups/document-upload-20261102';backup.mkdir(exist_ok=True)
assert not (backup/'compose-before').exists(),'Inspect previous release before retrying'
before=wrapper.read_bytes();old_proxy=caddy.read_bytes();(backup/'compose-before').write_bytes(before);(backup/'Caddyfile-before').write_bytes(old_proxy)
services=['ai-server-caddy-1','ai-server-moara-legal-mcp-1']
unchanged={s:json.loads(output(['docker','inspect',s]))[0] for s in services}
candidate=root/'infrastructure/uploads/Caddyfile-candidate'
subprocess.run(['docker','cp',str(candidate),'ai-server-caddy-1:/tmp/document-upload-Caddyfile'],check=True)
subprocess.run(['docker','exec','ai-server-caddy-1','caddy','validate','--config','/tmp/document-upload-Caddyfile','--adapter','caddyfile'],check=True)
overlay=root/'moara/infrastructure/document-upload-compose.yml';overlay.write_text('services:\n  moara-gateway:\n    image: '+tests['image']+'\n')
def up():
 subprocess.run(['sh',str(wrapper),'config','--quiet'],cwd=root,check=True)
 subprocess.run(['sh',str(wrapper),'up','-d','--no-deps','moara-gateway'],cwd=root,check=True)
 for _ in range(50):
  r=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c',"import urllib.request;assert urllib.request.urlopen('http://localhost:8075/api/v1/ready',timeout=3).status==200"],capture_output=True)
  if not r.returncode:return
  time.sleep(1)
 raise RuntimeError('Application readiness failed')
def proxy(data):
 # Preserve the inode of the bind-mounted configuration.
 with caddy.open('wb') as f:f.write(data)
 subprocess.run(['docker','kill','--signal=USR1','ai-server-caddy-1'],check=True)
try:
 wrapper.write_text(before.decode().replace(' "$@"',' \\\n -f moara/infrastructure/document-upload-compose.yml "$@"'));wrapper.chmod(0o755);up();proxy(candidate.read_bytes())
except Exception:
 wrapper.write_bytes(before);wrapper.chmod(0o755);up();proxy(old_proxy);raise
checks={}
for s in services:
 after=json.loads(output(['docker','inspect',s]))[0]
 checks[s+'_not_restarted']=after['Id']==unchanged[s]['Id'] and after['State']['StartedAt']==unchanged[s]['State']['StartedAt']
assert all(checks.values())
report={'published':True,'image':tests['image'],'unit_tests':tests['tests'],'checks':checks,'inference_restarted':False,'proxy_reload':'SIGUSR1'}
(root/'docs/runtime/document-upload-release.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
