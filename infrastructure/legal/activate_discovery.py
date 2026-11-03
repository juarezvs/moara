import pathlib,json,subprocess,time
root=pathlib.Path(__file__).resolve().parents[2];wrapper=root/'moara/infrastructure/scripts/compose.sh'
image=subprocess.check_output(['docker','image','inspect','moara-core:legal-discovery-20261031','--format','{{.Id}}'],text=True).strip()
for filename in ['legal-discovery-stage.json','unified-ui-stage.json']:
 report=json.loads((root/'docs/runtime'/filename).read_text());assert report['checks'] and all(report['checks'].values()) and report['tested_image_id']==image,filename
for service,base in [('ai-server-moara-gateway-1','moara-core:pre-legal-discovery-20261031'),('ai-server-moara-legal-mcp-1','moara-core:pre-mcp-discovery-20261031')]:
 assert subprocess.check_output(['docker','inspect',service,'--format','{{.Image}}'],text=True).strip()==subprocess.check_output(['docker','image','inspect',base,'--format','{{.Id}}'],text=True).strip()
assert 'Ran 139 tests' in (root/'tmp/legal-discovery-build.log').read_text()
backup=root/'backups/legal-discovery-20261031';backup.mkdir(exist_ok=True);before=wrapper.read_bytes();(backup/'compose-before').write_bytes(before)
(root/'moara/infrastructure/legal-discovery-compose.yml').write_text('services:\n  moara-gateway:\n    image: moara-core:legal-discovery-20261031\n  moara-legal-mcp:\n    image: moara-core:legal-discovery-20261031\n')
def up():
 subprocess.run(['sh',str(wrapper),'config','--quiet'],cwd=root,check=True)
 for name,container,port,path in [('moara-legal-mcp','ai-server-moara-legal-mcp-1',8076,'/health'),('moara-gateway','ai-server-moara-gateway-1',8075,'/api/v1/ready')]:
  subprocess.run(['sh',str(wrapper),'up','-d','--no-deps',name],cwd=root,check=True)
  for _ in range(40):
   code='import urllib.request;assert urllib.request.urlopen('+repr('http://localhost:'+str(port)+path)+',timeout=3).status==200'
   r=subprocess.run(['docker','exec',container,'python','-c',code],capture_output=True)
   if not r.returncode:break
   time.sleep(1)
  else:raise RuntimeError('Service readiness failed: '+name)
try:
 wrapper.write_text(before.decode().replace(' "$@"',' \\\n -f moara/infrastructure/legal-discovery-compose.yml "$@"'));wrapper.chmod(0o755);up()
except Exception:
 wrapper.write_bytes(before);wrapper.chmod(0o755);up();raise
print(json.dumps({'published':True,'image':image,'mcp_version':'0.5.0','inference_restarted':False,'data_migration':False}))
