import pathlib,subprocess,json,time
root=pathlib.Path(__file__).resolve().parents[2];wrapper=root/'moara/infrastructure/scripts/compose.sh';image=subprocess.check_output(['docker','image','inspect','moara-core:google-discovery-20261031','--format','{{.Id}}'],text=True).strip()
report=json.loads((root/'docs/runtime/google-discovery-stage.json').read_text());assert report['tested_mcp_image']==image and all(report['checks'].values())
regression=json.loads((root/'docs/runtime/google-app-stage.json').read_text());assert regression['tested_image_id']==image and all(regression['checks'].values())
assert 'Ran 173 tests' in (root/'tmp/google-discovery-build.log').read_text()
for service,base in [('ai-server-moara-gateway-1','moara-core:pre-google-app-20261031'),('ai-server-moara-legal-mcp-1','moara-core:pre-google-mcp-20261031')]:
 assert subprocess.check_output(['docker','inspect',service,'--format','{{.Image}}'],text=True).strip()==subprocess.check_output(['docker','image','inspect',base,'--format','{{.Id}}'],text=True).strip()
backup=root/'backups/google-discovery-20261031';backup.mkdir(exist_ok=True);before=wrapper.read_bytes();(backup/'compose-before').write_bytes(before)
def up(service,container,port,path):
 subprocess.run(['sh',str(wrapper),'up','-d','--no-deps',service],cwd=root,check=True)
 for _ in range(40):
  r=subprocess.run(['docker','exec',container,'python3','-c',f"import urllib.request;assert urllib.request.urlopen('http://localhost:{port}{path}',timeout=3).status==200"],capture_output=True)
  if not r.returncode:return
  time.sleep(1)
 raise RuntimeError('Service readiness failed: '+service)
try:
 wrapper.write_text(before.decode().replace(' "$@"',' \\\n -f moara/infrastructure/google-discovery-compose.yml "$@"'));wrapper.chmod(0o755)
 subprocess.run(['sh',str(wrapper),'config','--quiet'],cwd=root,check=True)
 up('moara-google-browser','ai-server-moara-google-browser-1',8077,'/health');up('moara-legal-mcp','ai-server-moara-legal-mcp-1',8076,'/health')
except Exception:
 wrapper.write_bytes(before);wrapper.chmod(0o755);up('moara-legal-mcp','ai-server-moara-legal-mcp-1',8076,'/health')
 subprocess.run(['docker','stop','ai-server-moara-google-browser-1'],capture_output=True);raise
print(json.dumps({'published':True,'mcp_version':'0.8.0','image':image,'google_search_operational':report['provider_result']['status']=='search_leads_retrieved','tested_provider_status':report['provider_result']['status'],'gateway_restarted':False,'inference_restarted':False}))
