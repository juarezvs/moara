"""Publish verified official-source integration; preserve core and MCP rollback."""
import pathlib,json,subprocess,time
root=pathlib.Path(__file__).resolve().parents[2]
for name in ['legal-sources-v2-live-stage.json','legal-sources-v2-ui-stage.json']:
 report=json.loads((root/'docs/runtime'/name).read_text());assert all(report['checks'].values()),name
lines=(root/'tmp/legal-sources-v2-prepublish-backup.log').read_text().splitlines()
assert any(line.startswith('{') and json.loads(line).get('verified') is True for line in lines),'Verified restoration required'
wrapper=root/'moara/infrastructure/scripts/compose.sh';backup=root/'backups/legal-sources-v2-20261030';backup.mkdir(exist_ok=True)
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
 if 'legal-sources-v2-compose.yml' not in text:text=text.replace(' "$@"',' \\\n -f moara/infrastructure/legal-sources-v2-compose.yml "$@"')
 wrapper.write_text(text);wrapper.chmod(0o755)
 subprocess.run(['sh',str(wrapper),'config','--quiet'],cwd=root,check=True)
 up('moara-legal-mcp',8076,'/health');up('moara-gateway',8075,'/api/v1/ready')
except Exception:
 wrapper.write_bytes((backup/'compose-before').read_bytes());wrapper.chmod(0o755)
 up('moara-legal-mcp',8076,'/health');up('moara-gateway',8075,'/api/v1/ready');raise
print(json.dumps({'published':True,'image':'moara-core:legal-sources-v2-20261030','mcp_version':'0.2.0','schema_changes':False,'inference_restarted':False}))
