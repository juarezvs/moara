import pathlib,json,subprocess,time
root=pathlib.Path(__file__).resolve().parents[2]
image=subprocess.check_output(['docker','image','inspect','moara-core:network-login-20261031','--format','{{.Id}}'],text=True).strip()
report=json.loads((root/'docs/runtime/unified-ui-stage.json').read_text())
assert all(report['checks'].values()) and report['tested_image_id']==image
previous=subprocess.check_output(['docker','image','inspect','moara-core:pre-network-login-20261031','--format','{{.Id}}'],text=True).strip()
assert subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()==previous
overlay=root/'moara/infrastructure/network-login-compose.yml';overlay.write_text('services:\n  moara-gateway:\n    image: moara-core:network-login-20261031\n')
wrapper=root/'moara/infrastructure/scripts/compose.sh';before=wrapper.read_bytes()
backup=root/'backups/network-login-20261031';backup.mkdir(exist_ok=True);(backup/'compose-before').write_bytes(before)
def up():
 subprocess.run(['sh',str(wrapper),'config','--quiet'],cwd=root,check=True)
 subprocess.run(['sh',str(wrapper),'up','-d','--no-deps','moara-gateway'],cwd=root,check=True)
 for _ in range(40):
  r=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c','import urllib.request;assert urllib.request.urlopen("http://localhost:8075/api/v1/ready",timeout=3).status==200'],capture_output=True)
  if not r.returncode:return
  time.sleep(1)
 raise RuntimeError('Gateway not ready')
try:
 wrapper.write_text(before.decode().replace(' "$@"',' \\\n -f moara/infrastructure/network-login-compose.yml "$@"'));wrapper.chmod(0o755);up()
except Exception:
 wrapper.write_bytes(before);wrapper.chmod(0o755);up();raise
print(json.dumps({'published':True,'image':image,'backend_changed':False,'inference_restarted':False}))
