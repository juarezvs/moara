import pathlib,json,subprocess,time
root=pathlib.Path(__file__).resolve().parents[2];wrapper=root/'moara/infrastructure/scripts/compose.sh'
image=subprocess.check_output(['docker','image','inspect','moara-core:stf-catalog-20261031','--format','{{.Id}}'],text=True).strip()
for filename in ['stf-catalog-stage.json','stf-catalog-ui-stage.json']:
 d=json.loads((root/'docs/runtime'/filename).read_text());assert d['tested_image_id']==image and all(d['checks'].values())
assert 'Ran 185 tests' in (root/'tmp/stf-catalog-build.log').read_text()
for service,base in [('ai-server-moara-gateway-1','moara-core:pre-stf-catalog-app-20261031'),('ai-server-moara-legal-mcp-1','moara-core:pre-stf-catalog-mcp-20261031')]:
 assert subprocess.check_output(['docker','inspect',service,'--format','{{.Image}}'],text=True).strip()==subprocess.check_output(['docker','image','inspect',base,'--format','{{.Id}}'],text=True).strip()
backup=root/'backups/stf-catalog-20261031';backup.mkdir(exist_ok=True);before=wrapper.read_bytes();(backup/'compose-before').write_bytes(before)
def up():
 subprocess.run(['sh',str(wrapper),'config','--quiet'],cwd=root,check=True)
 for service,container,port,path in [('moara-legal-mcp','ai-server-moara-legal-mcp-1',8076,'/health'),('moara-gateway','ai-server-moara-gateway-1',8075,'/api/v1/ready')]:
  subprocess.run(['sh',str(wrapper),'up','-d','--no-deps',service],cwd=root,check=True)
  for _ in range(40):
   r=subprocess.run(['docker','exec',container,'python','-c',f"import urllib.request;assert urllib.request.urlopen('http://localhost:{port}{path}',timeout=3).status==200"],capture_output=True)
   if not r.returncode:break
   time.sleep(1)
  else:raise RuntimeError('Readiness failed: '+service)
try:
 wrapper.write_text(before.decode().replace(' "$@"',' \\\n -f moara/infrastructure/stf-catalog-compose.yml "$@"'));wrapper.chmod(0o755);up()
except Exception:
 wrapper.write_bytes(before);wrapper.chmod(0o755);up();raise
print(json.dumps({'published':True,'image':image,'mcp_version':'0.9.0','catalogue_mounted_read_only':True,'inference_restarted':False,'database_migrations':False}))
