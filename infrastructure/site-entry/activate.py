"""Publish validated static assets and exact-root routing with rollback."""
import pathlib,subprocess,json,time
root=pathlib.Path(__file__).resolve().parents[2]
report=json.loads((root/'docs/runtime/primary-entry-stage.json').read_text())
assert report['checks'].get('stage_root_redirect_validated') and all(report['checks'].values())
lines=(root/'tmp/primary-entry-prepublish-backup.log').read_text().splitlines()
assert any(line.startswith('{') and json.loads(line).get('verified') is True for line in lines),'Verified restoration required'
wrapper=root/'moara/infrastructure/scripts/compose.sh';live=root/'infrastructure/caddy/Caddyfile'
backup=root/'backups/primary-entry-20261030';backup.mkdir(exist_ok=True)
if not (backup/'compose-before').exists():(backup/'compose-before').write_bytes(wrapper.read_bytes())
candidate=(root/'tmp/primary-entry/Caddyfile-candidate').read_text()
subprocess.run(['docker','exec','-i','ai-server-caddy-1','sh','-c','cat > /tmp/moara-primary-entry.Caddyfile && caddy validate --config /tmp/moara-primary-entry.Caddyfile --adapter caddyfile'],input=candidate,text=True,check=True)
def ready():
 for _ in range(40):
  r=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c','import urllib.request;assert urllib.request.urlopen("http://localhost:8075/api/v1/ready",timeout=3).status==200'],capture_output=True)
  if r.returncode==0:return
  time.sleep(1)
 raise RuntimeError('Gateway readiness failed')
try:
 text=wrapper.read_text()
 if 'site-entry-compose.yml' not in text:text=text.replace(' "$@"',' \\\n -f moara/infrastructure/site-entry-compose.yml "$@"')
 wrapper.write_text(text);wrapper.chmod(0o755)
 command=['sh',str(wrapper)]
 subprocess.run(command+['config','--quiet'],cwd=root,check=True)
 subprocess.run(command+['up','-d','--no-deps','moara-gateway'],cwd=root,check=True)
 ready()
 # Keep the bind-mounted inode. Admin API is disabled: restart only Caddy.
 live.write_text(candidate)
 subprocess.run(['docker','restart','ai-server-caddy-1'],check=True)
 time.sleep(2)
 assert subprocess.check_output(['docker','inspect','ai-server-caddy-1','--format','{{.State.Running}}'],text=True).strip()=='true'
except Exception:
 live.write_bytes((backup/'Caddyfile-before').read_bytes())
 wrapper.write_bytes((backup/'compose-before').read_bytes());wrapper.chmod(0o755)
 subprocess.run(['sh',str(wrapper),'up','-d','--no-deps','moara-gateway'],cwd=root,check=True)
 subprocess.run(['docker','restart','ai-server-caddy-1'],check=True)
 raise
print(json.dumps({'published':True,'image':'moara-core:primary-entry-20261030','ready':True,'inference_restarted':False,'database_migration':False,'root':'/moara/chat','legacy':'/?interface=anterior'}))
