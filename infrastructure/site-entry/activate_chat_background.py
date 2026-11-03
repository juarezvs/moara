import pathlib,json,subprocess,time
root=pathlib.Path(__file__).resolve().parents[2];wrapper=root/'moara/infrastructure/scripts/compose.sh'
image=subprocess.check_output(['docker','image','inspect','moara-core:chat-background-20261102','--format','{{.Id}}'],text=True).strip()
for name in ['chat-background-ui-stage.json','chat-background-code-stage.json']:
 r=json.loads((root/'docs/runtime'/name).read_text());assert r['tested_image_id']==image and r['checks'] and all(r['checks'].values())
baseline=subprocess.check_output(['docker','image','inspect','moara-core:pre-chat-background-app-20261102','--format','{{.Id}}'],text=True).strip()
assert subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()==baseline
backup=root/'backups/chat-background-20261102';backup.mkdir(exist_ok=True);before=wrapper.read_bytes();(backup/'compose-before').write_bytes(before)
def up():
 subprocess.run(['sh',str(wrapper),'config','--quiet'],cwd=root,check=True)
 subprocess.run(['sh',str(wrapper),'up','-d','--no-deps','moara-gateway'],cwd=root,check=True)
 for _ in range(45):
  r=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c',"import urllib.request;assert urllib.request.urlopen('http://localhost:8075/api/v1/ready',timeout=3).status==200"],capture_output=True)
  if not r.returncode:return
  time.sleep(1)
 raise RuntimeError('Gateway did not become ready')
try:
 wrapper.write_text(before.decode().replace(' "$@"',' \\\n -f moara/infrastructure/chat-background-compose.yml "$@"'));wrapper.chmod(0o755);up()
except Exception:
 wrapper.write_bytes(before);wrapper.chmod(0o755);up();raise
print(json.dumps({'published':True,'image':image,'frontend_only':True,'mcp_restarted':False,'inference_restarted':False,'database_migrations':False}))
