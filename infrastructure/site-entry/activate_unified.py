"""Publish one chat surface, retaining a precise gateway/proxy rollback."""
import pathlib,subprocess,json,time,hashlib
root=pathlib.Path(__file__).resolve().parents[2];wrapper=root/'moara/infrastructure/scripts/compose.sh';live=root/'infrastructure/caddy/Caddyfile';backup=root/'backups/unified-20261031'
expected=subprocess.check_output(['docker','image','inspect','moara-core:pre-unified-20261031','--format','{{.Id}}'],text=True).strip()
current=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip();assert current==expected,'Production changed since snapshot'
image=subprocess.check_output(['docker','image','inspect','moara-core:unified-20261031','--format','{{.Id}}'],text=True).strip()
report=json.loads((root/'docs/runtime/unified-ui-stage.json').read_text());assert report['checks'] and all(report['checks'].values()) and report['tested_image_id']==image
routes=json.loads((root/'docs/runtime/unified-routes-stage.json').read_text());assert all(routes['checks'].values())
assert 'Ran 119 tests' in (root/'tmp/unified-build.log').read_text()
lines=(root/'tmp/unified-prepublish-backup.log').read_text().splitlines();assert any(line.startswith('{') and json.loads(line).get('verified') is True for line in lines)
assert live.read_bytes()==(backup/'Caddyfile-before').read_bytes(),'Proxy changed since preparation'
if not (backup/'compose-before').exists():(backup/'compose-before').write_bytes(wrapper.read_bytes())
candidate=(root/'tmp/unified-proxy/Caddyfile-candidate').read_text()
subprocess.run(['docker','exec','-i','ai-server-caddy-1','sh','-c','cat > /tmp/moara-unified.Caddyfile && caddy validate --config /tmp/moara-unified.Caddyfile --adapter caddyfile'],input=candidate,text=True,check=True,capture_output=True)
def up():
 subprocess.run(['sh',str(wrapper),'config','--quiet'],cwd=root,check=True)
 subprocess.run(['sh',str(wrapper),'up','-d','--no-deps','moara-gateway'],cwd=root,check=True)
 for _ in range(40):
  r=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c','import urllib.request;assert urllib.request.urlopen("http://localhost:8075/api/v1/ready",timeout=3).status==200'],capture_output=True)
  if not r.returncode:return
  time.sleep(1)
 raise RuntimeError('Gateway not ready')
try:
 text=wrapper.read_text()
 if 'unified-compose.yml' not in text:text=text.replace(' "$@"',' \\\n -f moara/infrastructure/unified-compose.yml "$@"')
 wrapper.write_text(text);wrapper.chmod(0o755);up()
 live.write_text(candidate)
 subprocess.run(['docker','restart','ai-server-caddy-1'],check=True,capture_output=True);time.sleep(2)
 assert subprocess.check_output(['docker','inspect','ai-server-caddy-1','--format','{{.State.Running}}'],text=True).strip()=='true'
except Exception:
 wrapper.write_bytes((backup/'compose-before').read_bytes());wrapper.chmod(0o755);live.write_bytes((backup/'Caddyfile-before').read_bytes());up();subprocess.run(['docker','restart','ai-server-caddy-1'],check=True,capture_output=True);raise
print(json.dumps({'published':True,'image':'moara-core:unified-20261031','root':'/moara/chat','one_public_chat':True,'data_migration':False,'inference_restarted':False,'mcp_restarted':False}))
