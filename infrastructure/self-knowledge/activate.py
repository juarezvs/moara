import pathlib,json,subprocess,time
root=pathlib.Path(__file__).resolve().parents[2];wrapper=root/'moara/infrastructure/scripts/compose.sh'
image=subprocess.check_output(['docker','image','inspect','moara-core:self-knowledge-20261102','--format','{{.Id}}'],text=True).strip()
for name in ['self-knowledge-stage.json','self-knowledge-legal-stage.json','self-knowledge-preservation.json']:
 d=json.loads((root/'docs/runtime'/name).read_text());assert d['tested_image_id']==image and d['checks'] and all(d['checks'].values())
test=json.loads((root/'tmp/self-knowledge-tests.json').read_text());assert test['passed'] and test['tests']>=236 and test['image']==image
for service,base in [('ai-server-moara-gateway-1','moara-core:pre-self-knowledge-app-20261102'),('ai-server-moara-legal-mcp-1','moara-core:pre-self-knowledge-mcp-20261102')]:
 assert subprocess.check_output(['docker','inspect',service,'--format','{{.Image}}'],text=True).strip()==subprocess.check_output(['docker','image','inspect',base,'--format','{{.Id}}'],text=True).strip()
backup=root/'backups/self-knowledge-20261102';backup.mkdir(exist_ok=True);before=wrapper.read_bytes();(backup/'compose-before').write_bytes(before)
def up():
 subprocess.run(['sh',str(wrapper),'config','--quiet'],cwd=root,check=True)
 subprocess.run(['sh',str(wrapper),'up','-d','--no-deps','moara-gateway'],cwd=root,check=True)
 for _ in range(40):
  r=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c',"import urllib.request;assert urllib.request.urlopen('http://localhost:8075/api/v1/ready',timeout=3).status==200"],capture_output=True)
  if not r.returncode:return
  time.sleep(1)
 raise RuntimeError('Gateway readiness failed')
try:
 wrapper.write_text(before.decode().replace(' "$@"',' \\\n -f moara/infrastructure/self-knowledge-compose.yml "$@"'));wrapper.chmod(0o755);up()
except Exception:
 wrapper.write_bytes(before);wrapper.chmod(0o755);up();raise
print(json.dumps({'published':True,'image':image,'gateway_only':True,'inference_restarted':False,'database_migrations':False}))
