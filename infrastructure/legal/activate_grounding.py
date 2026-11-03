"""Publish verified official-source integration; preserve core and MCP rollback."""
import pathlib,json,subprocess,time
root=pathlib.Path(__file__).resolve().parents[2]
for name in ['legal-grounding-stage.json','legal-grounding-ui.json']:
 report=json.loads((root/'docs/runtime'/name).read_text());assert all(report['checks'].values()),name
image=subprocess.check_output(['docker','image','inspect','moara-core:legal-grounding-20261031','--format','{{.Id}}'],text=True).strip()
checked=json.loads((root/'docs/runtime/legal-grounding-stage.json').read_text())
assert checked['tested_image_id']==image,'Stage evidence must match image being published'
current=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
expected=subprocess.check_output(['docker','image','inspect','moara-core:pre-legal-grounding-20261031','--format','{{.Id}}'],text=True).strip()
assert current==expected,'Production changed since candidate snapshot'
assert 'Ran 111 tests' in (root/'tmp/legal-grounding-build.log').read_text()
lines=(root/'tmp/legal-grounding-prepublish-backup.log').read_text().splitlines()
assert any(line.startswith('{') and json.loads(line).get('verified') is True for line in lines),'Verified restoration required'
wrapper=root/'moara/infrastructure/scripts/compose.sh';backup=root/'backups/legal-grounding-20261031';backup.mkdir(exist_ok=True)
if not (backup/'compose-before').exists():(backup/'compose-before').write_bytes(wrapper.read_bytes())
def up(service,port,path):
 subprocess.run(['sh',str(wrapper),'up','-d','--no-deps',service],cwd=root,check=True)
 for _ in range(45):
  r=subprocess.run(['docker','exec','ai-server-'+service+'-1','python','-c','import urllib.request;assert urllib.request.urlopen('+repr(f'http://localhost:{port}{path}')+',timeout=3).status==200'],capture_output=True)
  if r.returncode==0:return
  time.sleep(1)
 raise RuntimeError('Readiness check failed: '+service)
try:
 text=wrapper.read_text()
 if 'legal-grounding-compose.yml' not in text:text=text.replace(' "$@"',' \\\n -f moara/infrastructure/legal-grounding-compose.yml "$@"')
 wrapper.write_text(text);wrapper.chmod(0o755)
 subprocess.run(['sh',str(wrapper),'config','--quiet'],cwd=root,check=True)
 up('moara-legal-mcp',8076,'/health');up('moara-gateway',8075,'/api/v1/ready')
except Exception:
 wrapper.write_bytes((backup/'compose-before').read_bytes());wrapper.chmod(0o755)
 up('moara-legal-mcp',8076,'/health');up('moara-gateway',8075,'/api/v1/ready');raise
print(json.dumps({'published':True,'image':'moara-core:legal-grounding-20261031','mcp_version':'0.4.0','schema_changes':False,'inference_restarted':False}))
