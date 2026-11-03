import pathlib,json,subprocess,time
root=pathlib.Path(__file__).resolve().parents[2];wrapper=root/'moara/infrastructure/scripts/compose.sh'
image=subprocess.check_output(['docker','image','inspect','moara-core:chat-stream-20261102','--format','{{.Id}}'],text=True).strip()
tests=json.loads((root/'tmp/chat-stream-tests.json').read_text())
ui=json.loads((root/'docs/runtime/chat-stream-ui-stage.json').read_text())
assert tests['passed'] and tests['tests']>=264 and tests['image']==image
assert ui['tested_image_id']==image and ui['checks'] and all(ui['checks'].values())
citations=json.loads((root/'docs/runtime/chat-stream-citations-stage.json').read_text());assert citations['tested_image_id']==image and all(citations['checks'].values())
assert '10 passed' in __import__('re').sub(r'\x1b\[[0-9;]*m','',(root/'tmp/chat-stream-unit.log').read_text())
base=subprocess.check_output(['docker','image','inspect','moara-core:pre-chat-stream-app-20261102','--format','{{.Id}}'],text=True).strip()
assert subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()==base
backup=root/'backups/chat-stream-20261102';backup.mkdir(exist_ok=True)
before=wrapper.read_bytes();(backup/'compose-before').write_bytes(before)
def up():
 subprocess.run(['sh',str(wrapper),'config','--quiet'],cwd=root,check=True)
 subprocess.run(['sh',str(wrapper),'up','-d','--no-deps','moara-gateway'],cwd=root,check=True)
 for _ in range(40):
  r=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c',"import urllib.request;assert urllib.request.urlopen('http://localhost:8075/api/v1/ready',timeout=3).status==200"],capture_output=True)
  if not r.returncode:return
  time.sleep(1)
 raise RuntimeError('Gateway readiness failed')
try:
 wrapper.write_text(before.decode().replace(' "$@"',' \\\n -f moara/infrastructure/chat-stream-compose.yml "$@"'));wrapper.chmod(0o755);up()
except Exception:
 wrapper.write_bytes(before);wrapper.chmod(0o755);up();raise
print(json.dumps({'published':True,'image':image,'gateway_only':True,'inference_restarted':False,'database_migrations':False}))
