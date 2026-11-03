"""Publish only the approved right rail and progress transport; retain rollback."""
import pathlib,subprocess,json,time
root=pathlib.Path(__file__).resolve().parents[2]
for filename in ['ide-sdk-stage.json','ide-ui.json']:
 report=json.loads((root/'docs/runtime'/filename).read_text())
 assert report['checks'] and all(report['checks'].values()),filename
assert 'Ran 89 tests' in (root/'tmp/ide-build.log').read_text()
current=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
expected=subprocess.check_output(['docker','image','inspect','moara-core:pre-ide-20261030','--format','{{.Id}}'],text=True).strip()
assert current==expected,'Production changed since candidate snapshot'
lines=(root/'tmp/ide-prepublish-backup.log').read_text().splitlines()
assert any(line.startswith('{') and json.loads(line).get('verified') is True for line in lines),'Verified restoration required'
wrapper=root/'moara/infrastructure/scripts/compose.sh';backup=root/'backups/ide-20261030';backup.mkdir(exist_ok=True)
if not (backup/'compose-before').exists():(backup/'compose-before').write_bytes(wrapper.read_bytes())
def up():
 subprocess.run(['sh',str(wrapper),'config','--quiet'],cwd=root,check=True)
 subprocess.run(['sh',str(wrapper),'up','-d','--no-deps','moara-gateway'],cwd=root,check=True)
 for _ in range(40):
  if subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c','import urllib.request;assert urllib.request.urlopen("http://localhost:8075/api/v1/ready",timeout=3).status==200'],capture_output=True).returncode==0:return
  time.sleep(1)
 raise RuntimeError('Gateway did not become ready')
try:
 text=wrapper.read_text()
 if 'ide-compose.yml' not in text:text=text.replace(' "$@"',' \\\n -f moara/infrastructure/ide-compose.yml "$@"')
 wrapper.write_text(text);wrapper.chmod(0o755);up()
except Exception:
 wrapper.write_bytes((backup/'compose-before').read_bytes());wrapper.chmod(0o755);up();raise
print(json.dumps({'published':True,'image':'moara-core:ide-20261030','ready':True,'schema_changes':False,'inference_restarted':False}))
