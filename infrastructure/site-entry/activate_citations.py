import pathlib,json,subprocess,time
root=pathlib.Path(__file__).resolve().parents[2];wrapper=root/'moara/infrastructure/scripts/compose.sh'
image=subprocess.check_output(['docker','image','inspect','moara-core:citations-v2-20261031','--format','{{.Id}}'],text=True).strip()
report=json.loads((root/'docs/runtime/citations-ui-stage.json').read_text())
assert report['tested_image_id']==image and all(report['checks'].values())
for key in ['source_hint_matches_inline_citation','source_hint_keyboard_and_escape','source_hint_mobile_inside_viewport','source_hint_touch_can_close']:assert report['checks'][key]
assert 'Ran 163 tests' in (root/'tmp/citations-build.log').read_text()
before=wrapper.read_bytes();backup=root/'backups/citations-v2-20261031';backup.mkdir(exist_ok=True);(backup/'compose-before').write_bytes(before)
expected=subprocess.check_output(['docker','image','inspect','moara-core:pre-citations-20261031','--format','{{.Id}}'],text=True).strip()
current=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
prior=json.loads((root/'docs/runtime/citations-ui-public.json').read_text());assert current==prior['tested_image_id'] and all(prior['checks'].values())
(root/'moara/infrastructure/citations-v2-compose.yml').write_text('services:\n  moara-gateway:\n    image: moara-core:citations-v2-20261031\n')
def up():
 subprocess.run(['sh',str(wrapper),'config','--quiet'],cwd=root,check=True)
 subprocess.run(['sh',str(wrapper),'up','-d','--no-deps','moara-gateway'],cwd=root,check=True)
 for _ in range(40):
  r=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c',"import urllib.request;assert urllib.request.urlopen('http://localhost:8075/api/v1/ready',timeout=3).status==200"],capture_output=True)
  if not r.returncode:return
  time.sleep(1)
 raise RuntimeError('Gateway readiness failed')
try:
 wrapper.write_text(before.decode().replace(' "$@"',' \\\n -f moara/infrastructure/citations-v2-compose.yml "$@"'));wrapper.chmod(0o755);up()
except Exception:
 wrapper.write_bytes(before);wrapper.chmod(0o755);up();raise
print(json.dumps({'published':True,'image':image,'mcp_restarted':False,'inference_restarted':False}))
