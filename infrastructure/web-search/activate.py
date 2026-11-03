import pathlib,subprocess,json,time
root=pathlib.Path(__file__).resolve().parents[2];wrapper=root/'moara/infrastructure/scripts/compose.sh'
tests=json.loads((root/'tmp/public-web-tests.json').read_text());live=json.loads((root/'docs/runtime/public-web-live-stage.json').read_text())
assert tests['passed'] and tests['tests']>=275 and all(live['checks'].values())
ui=json.loads((root/'docs/runtime/public-web-ui-stage.json').read_text())
assert all(ui['checks'].values()) and ui['tested_image_id']==tests['images']['ai-server-moara-gateway-1']
for service,name,tag in [('ai-server-moara-gateway-1','core','moara-core:public-web-app-20261102'),('ai-server-moara-legal-mcp-1','mcp','moara-core:public-web-mcp-20261102')]:
 image=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip()
 assert image==tests['images'][service]==live['images'][name]
 previous_file=root/'docs/runtime/public-web-release-before-catalog-fix.json'
 current=subprocess.check_output(['docker','inspect',service,'--format','{{.Image}}'],text=True).strip()
 if previous_file.exists():assert current==json.loads(previous_file.read_text())[service]
 else:
  base='moara-core:pre-public-web-'+('app' if name=='core' else 'mcp')+'-20261102'
  assert current==subprocess.check_output(['docker','image','inspect',base,'--format','{{.Id}}'],text=True).strip()
backup=root/'backups/public-web-20261102';backup.mkdir(exist_ok=True)
before=wrapper.read_bytes();stamp=str(time.time_ns());(backup/('compose-before-'+stamp)).write_bytes(before)
rollback='services:\n'
for service,label in [('ai-server-moara-gateway-1','moara-gateway'),('ai-server-moara-legal-mcp-1','moara-legal-mcp')]:
 current=subprocess.check_output(['docker','inspect',service,'--format','{{.Image}}'],text=True).strip()
 tag='moara-core:public-web-rollback-'+label+'-'+stamp
 if subprocess.run(['docker','image','inspect',current],capture_output=True).returncode:
  # Keep the known-good pre-change release as rollback when the old OCI index
  # of a running intermediate release is no longer addressable by the daemon.
  baseline='moara-core:pre-public-web-'+('app' if label=='moara-gateway' else 'mcp')+'-20261102'
  subprocess.run(['docker','tag',baseline,tag],check=True)
 else:subprocess.run(['docker','tag',current,tag],check=True)
 rollback+='  '+label+':\n    image: '+tag+'\n'
rollback_file=backup/('rollback-'+stamp+'.yml');rollback_file.write_text(rollback)
def up():
 subprocess.run(['sh',str(wrapper),'config','--quiet'],cwd=root,check=True)
 subprocess.run(['sh',str(wrapper),'up','-d','--no-deps','moara-legal-mcp','moara-gateway'],cwd=root,check=True)
 for name,port,path in [('ai-server-moara-legal-mcp-1',8076,'/health'),('ai-server-moara-gateway-1',8075,'/api/v1/ready')]:
  for _ in range(45):
   r=subprocess.run(['docker','exec',name,'python','-c',f"import urllib.request;assert urllib.request.urlopen('http://localhost:{port}{path}',timeout=3).status==200"],capture_output=True)
   if r.returncode==0:break
   time.sleep(1)
  else:raise RuntimeError('Readiness failed')
try:
 wrapper.write_text(before.decode() if 'public-web-compose.yml' in before.decode() else before.decode().replace(' "$@"',' \\\n -f moara/infrastructure/public-web-compose.yml "$@"'));wrapper.chmod(0o755);up()
except Exception:
 wrapper.write_text(before.decode().replace(' "$@"',' \\\n -f '+str(rollback_file.relative_to(root))+' "$@"'));wrapper.chmod(0o755);up();raise
print(json.dumps({'published':True,'inference_restarted':False,'database_migrations':False}))
