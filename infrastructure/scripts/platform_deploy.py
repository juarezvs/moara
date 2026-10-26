"""Publish only the tested gateway candidate after verified encrypted restore."""
import hashlib,json,os,shutil,ssl,subprocess,time,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('/home/nutec/ai-server');STAGE=Path('/home/nutec/moara-platform-20261026')
RELEASE=ROOT/'docs/runtime/platform-release-20261026';RELEASE.mkdir(mode=0o700,exist_ok=True)
BEFORE=RELEASE/'before';BEFORE.mkdir(mode=0o700,exist_ok=True)
def run(args,timeout=180):
 p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
 if p.returncode:
  diagnostic=RELEASE/'operation-error.log';diagnostic.write_text(p.stderr[-12000:]);diagnostic.chmod(0o600)
  raise RuntimeError('release_operation_failed; private diagnostic retained')
 return p.stdout
backup=json.loads((ROOT/'docs/runtime/moara-preservation-latest.json').read_text())
if not backup.get('verified'):raise RuntimeError('verified_backup_required')
if (datetime.now(timezone.utc)-datetime.fromisoformat(backup['verified_at'].replace('Z','+00:00'))).total_seconds()>14400:raise RuntimeError('recent_backup_required')
containers=json.loads(run(['docker','ps','--format','json']).replace('\n','\n')) if False else [json.loads(line) for line in run(['docker','ps','--format','json']).splitlines()]
before_ids={r['Names']:r['ID'] for r in containers if r['Names'].startswith('ai-server-')}
old_image=run(['docker','inspect','-f','{{.Image}}','ai-server-moara-gateway-1']).strip()
new_image=run(['docker','image','inspect','-f','{{.Id}}','moara-core:platform-20261026']).strip()
manifest=json.loads((STAGE/'release-manifest.json').read_text())
for name,checksum in manifest['files'].items():
 if hashlib.sha256((STAGE/name).read_bytes()).hexdigest()!=checksum:raise RuntimeError('candidate_source_hash_mismatch')
 if not (ROOT/name).resolve().is_relative_to(ROOT.resolve()):raise RuntimeError('unsafe_source_path')
expected={name:checksum for name,checksum in manifest['files'].items() if name.startswith(('moara/gateway/','moara/identity/')) and name.endswith(('.py','.sql'))}
check_code="import hashlib,json;from pathlib import Path;expected="+repr(expected)+";assert all(hashlib.sha256((Path('/app')/n).read_bytes()).hexdigest()==h for n,h in expected.items())"
run(['docker','run','--rm','--network','none','--read-only','--memory','256m','moara-core:platform-20261026','python','-c',check_code])
def preserve(path):
 relative=path.relative_to(ROOT);dest=BEFORE/relative
 if path.exists() and not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
for name in manifest['files']:
 source=STAGE/name;target=ROOT/name
 if target.exists() and source.read_bytes()==target.read_bytes():continue
 preserve(target);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
# Preserve built assets and index separately; old hashed assets are retained.
for source in (STAGE/'moara/web/dist/moara-web/browser').rglob('*'):
 if source.is_file():
  target=ROOT/'moara/web/dist/moara-web/browser'/source.relative_to(STAGE/'moara/web/dist/moara-web/browser')
  preserve(target);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
overlay=ROOT/'moara/infrastructure/platform-compose.yml';preserve(overlay)
overlay.write_text("services:\n  moara-gateway:\n    image: moara-core:platform-20261026\n    environment:\n      MOARA_SANDBOX_READY: 'true'\n  moara-migrate:\n    image: moara-core:platform-20261026\n")
helper=ROOT/'moara/infrastructure/scripts/compose.sh';preserve(helper)
original=helper.read_text()
if '-f moara/infrastructure/platform-compose.yml' not in original:
 helper.write_text(original.replace('moara/infrastructure/public-site-compose.yml "$@"','moara/infrastructure/public-site-compose.yml \\\n -f moara/infrastructure/platform-compose.yml "$@"'))
def compose(*args):return run(['sh',str(helper),*args],timeout=240)
(RELEASE/'before-state.json').write_text(json.dumps({'containers':before_ids,'gateway_image':old_image,'candidate_image':new_image,'backup':backup},indent=2))
try:
 compose('run','--rm','--no-deps','moara-migrate')
 compose('up','-d','--no-deps','--no-build','--pull','never','moara-gateway')
 deadline=time.monotonic()+90
 while time.monotonic()<deadline:
  p=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c','import urllib.request;urllib.request.urlopen("http://localhost:8075/api/v1/ready",timeout=3)'],capture_output=True)
  if p.returncode==0:break
  time.sleep(2)
 else:raise RuntimeError('gateway_readiness_failed')
 tls=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/moara-domain-root-ca.crt'));routes={}
 for path,expected in [('/',200),('/moara/',200),('/studio/',200),('/moara/api/v1/health',200),('/moara/api/v1/platform/resources',401)]:
  try:
   with urllib.request.urlopen('https://moara.am.trf1.gov.br'+path,context=tls,timeout=20) as response:status=response.status
  except urllib.error.HTTPError as exc:status=exc.code
  routes[path]=status
  if status!=expected:raise RuntimeError('public_route_check_failed')
except Exception:
 rollback=RELEASE/'rollback-compose.yml';rollback.write_text('services:\n  moara-gateway:\n    image: '+old_image+"\n    environment:\n      MOARA_SANDBOX_READY: 'false'\n")
 run(['sh',str(helper),'-f',str(rollback),'up','-d','--no-deps','--no-build','--pull','never','moara-gateway'],timeout=240)
 for source in BEFORE.rglob('*'):
  if source.is_file():shutil.copy2(source,ROOT/source.relative_to(BEFORE))
 raise
worker=ROOT/'infrastructure/scripts/sandbox_worker.py';preserve(worker);shutil.copy2(STAGE/'sandbox_worker.py',worker)
units=Path.home()/'.config/systemd/user';units.mkdir(parents=True,exist_ok=True);unit=units/'moara-sandbox-worker.service'
if unit.exists() and '# MOARA managed sandbox worker' not in unit.read_text():raise RuntimeError('unowned_systemd_unit')
unit.write_text(f"""# MOARA managed sandbox worker
[Unit]
Description=Moara approved rootless code execution worker
After=ai-server.service
[Service]
Type=simple
WorkingDirectory={ROOT}
Environment=DOCKER_HOST=unix:///run/user/{os.getuid()}/docker.sock
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 {worker}
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true
MemoryMax=512M
TasksMax=64
[Install]
WantedBy=default.target
""")
run(['systemctl','--user','daemon-reload']);run(['systemctl','--user','enable','--now','moara-sandbox-worker.service'])
if run(['systemctl','--user','is-active','moara-sandbox-worker.service']).strip()!='active':raise RuntimeError('sandbox_worker_not_active')
after={r['Names']:r['ID'] for r in [json.loads(line) for line in run(['docker','ps','--format','json']).splitlines()] if r['Names'].startswith('ai-server-')}
changed=[name for name in before_ids if before_ids[name]!=after.get(name)]
if changed!=['ai-server-moara-gateway-1']:raise RuntimeError('unexpected_container_changes')
report={'published_at':datetime.now(timezone.utc).isoformat(),'image_id':new_image,'previous_image_id':old_image,
 'migration':'0005_platform','backup':backup,'public_routes':routes,'changed_containers':changed,'preserved_containers':len(before_ids)-1,
 'sandbox_worker':'active','rollback_directory':str(BEFORE),'synthetic_records_imported':False,'host_rebooted':False}
(RELEASE/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
