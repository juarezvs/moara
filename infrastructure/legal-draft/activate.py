import pathlib,json,subprocess,time
root=pathlib.Path(__file__).resolve().parents[2];wrapper=root/'moara/infrastructure/scripts/compose.sh'
tests=json.loads((root/'tmp/legal-draft-tests.json').read_text());stage=json.loads((root/'tmp/legal-draft-stage.json').read_text())
assert tests['passed'] and tests['tests']>=299
for label,service in [('core','ai-server-moara-gateway-1'),('mcp','ai-server-moara-legal-mcp-1')]:
 assert subprocess.check_output(['docker','inspect',stage[label],'--format','{{.Image}}'],text=True).strip()==tests['images'][service]
live=json.loads((root/'docs/runtime/legal-draft-live-stage.json').read_text());ui=json.loads((root/'docs/runtime/legal-draft-ui-stage.json').read_text())
assert all(live['checks'].values()) and live['images']=={k:tests['images'][v] for k,v in [('core','ai-server-moara-gateway-1'),('mcp','ai-server-moara-legal-mcp-1')]}
assert all(ui['checks'].values()) and ui['tested_image_id']==live['images']['core']
for service,base in [('ai-server-moara-gateway-1','moara-core:pre-legal-draft-app-20261102-r2'),('ai-server-moara-legal-mcp-1','moara-core:pre-legal-draft-mcp-20261102')]:
 assert subprocess.check_output(['docker','inspect',service,'--format','{{.Image}}'],text=True).strip()==subprocess.check_output(['docker','image','inspect',base,'--format','{{.Id}}'],text=True).strip()
backup=root/'backups/legal-draft-20261102';backup.mkdir(exist_ok=True)
assert not (backup/'compose-before').exists(),'Release already attempted; inspect before retrying'
before=wrapper.read_bytes();(backup/'compose-before').write_bytes(before)

def up():
 subprocess.run(['sh',str(wrapper),'config','--quiet'],cwd=root,check=True)
 subprocess.run(['sh',str(wrapper),'up','-d','--no-deps','moara-gateway','moara-legal-mcp'],cwd=root,check=True)
 for service,port,path in [('ai-server-moara-gateway-1',8075,'/api/v1/ready'),('ai-server-moara-legal-mcp-1',8076,'/health')]:
  for _ in range(45):
   r=subprocess.run(['docker','exec',service,'python','-c',f"import urllib.request;assert urllib.request.urlopen('http://localhost:{port}{path}',timeout=3).status==200"],capture_output=True)
   if not r.returncode:break
   time.sleep(1)
  else:raise RuntimeError('Release readiness failed')
try:
 wrapper.write_text(before.decode().replace(' "$@"',' \\\n -f moara/infrastructure/legal-draft-compose.yml "$@"'));wrapper.chmod(0o755);up()
except Exception:
 wrapper.write_bytes(before);wrapper.chmod(0o755);up();raise
report={'published':True,'images':live['images'],'unit_tests':tests['tests'],'database_migrations':False,'inference_restarted':False}
(root/'docs/runtime/legal-draft-release.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
