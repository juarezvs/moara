"""Publish only the qualified web assets, retaining the current backend and MCP."""
import pathlib,json,subprocess,time,re
root=pathlib.Path(__file__).resolve().parents[2]
wrapper=root/'moara/infrastructure/scripts/compose.sh'
image=subprocess.check_output(['docker','image','inspect','moara-core:page-scroll-20261102','--format','{{.Id}}'],text=True).strip()
ui=json.loads((root/'docs/runtime/page-scroll-ui-stage.json').read_text())
assert ui['tested_image_id']==image and ui['checks'] and all(ui['checks'].values())
unit=re.sub(r'\x1b\[[0-9;]*m','',(root/'tmp/page-scroll-angular.log').read_text())
assert '10 passed' in unit and 'Application bundle generation complete' in unit
baseline=subprocess.check_output(['docker','image','inspect','moara-core:pre-page-scroll-app-20261102','--format','{{.Id}}'],text=True).strip()
assert subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()==baseline
backup=root/'backups/page-scroll-20261102';backup.mkdir(exist_ok=True)
before=wrapper.read_bytes()
assert not (backup/'compose-before').exists(), 'Release already attempted; inspect before retrying'
(backup/'compose-before').write_bytes(before)
mcp_before=subprocess.check_output(['docker','inspect','ai-server-moara-legal-mcp-1','--format','{{.Id}} {{.State.StartedAt}}'],text=True).strip()

def up():
 subprocess.run(['sh',str(wrapper),'config','--quiet'],cwd=root,check=True)
 subprocess.run(['sh',str(wrapper),'up','-d','--no-deps','moara-gateway'],cwd=root,check=True)
 for _ in range(45):
  r=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c',"import urllib.request;assert urllib.request.urlopen('http://localhost:8075/api/v1/ready',timeout=3).status==200"],capture_output=True)
  if not r.returncode:return
  time.sleep(1)
 raise RuntimeError('Gateway readiness failed')

try:
 assert ' -f moara/infrastructure/page-scroll-compose.yml' not in before.decode()
 wrapper.write_text(before.decode().replace(' "$@"',' \\\n -f moara/infrastructure/page-scroll-compose.yml "$@"'))
 wrapper.chmod(0o755);up()
 assert subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()==image
 assert subprocess.check_output(['docker','inspect','ai-server-moara-legal-mcp-1','--format','{{.Id}} {{.State.StartedAt}}'],text=True).strip()==mcp_before
except Exception:
 wrapper.write_bytes(before);wrapper.chmod(0o755);up();raise
report={'published':True,'image':image,'baseline':baseline,'frontend_only':True,'mcp_restarted':False,'inference_restarted':False,'database_migrations':False}
(root/'docs/runtime/page-scroll-release.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
