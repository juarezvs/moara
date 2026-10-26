import base64,json,subprocess,shlex
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
files=['moara/infrastructure/scripts/config_snapshot.py','moara/infrastructure/scripts/preservation.py','infrastructure/scripts/backup.sh','infrastructure/scripts/start-services.sh','infrastructure/scripts/deploy.sh','infrastructure/systemd/ai-server.service','infrastructure/systemd/ai-backup.service','tests/operations/test_config_snapshot.py']
payload={name:base64.b64encode((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).decode() for name in files}
remote = r"""import base64,datetime,json,os,pathlib,shutil,subprocess,sys
os.umask(0o077)
payload=json.load(sys.stdin)
base=pathlib.Path('/home/nutec/moara-phase1')/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
base.mkdir(parents=True,mode=0o700)
for name,content in payload.items():
 p=base/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(content))
root=pathlib.Path('/home/nutec/ai-server')
before=base/'before';before.mkdir()
for name in ['ai-server.service','ai-backup.service']:
 shutil.copy2(pathlib.Path('/home/nutec/.config/systemd/user')/name,before/name)
for name in ['moara/infrastructure/scripts/preservation.py','infrastructure/scripts/backup.sh','infrastructure/scripts/deploy.sh']:
 p=before/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/name,p)
state=subprocess.run(['docker','ps','--no-trunc','--format','{{.Names}} {{.ID}} {{.Image}}'],capture_output=True,check=True,text=True).stdout
(base/'containers-before.txt').write_text(state)
r=subprocess.run(['python3','-m','unittest','discover','-s',str(base/'tests/operations'),'-v'],capture_output=True,text=True)
(base/'unit-tests.log').write_text(r.stdout+r.stderr)
print(json.dumps({'stage':str(base),'tests_exit':r.returncode,'tests':r.stdout+r.stderr}))
if r.returncode:raise SystemExit(r.returncode)
for name in ['infrastructure/scripts/backup.sh','infrastructure/scripts/start-services.sh','infrastructure/scripts/deploy.sh']:
 subprocess.run(['bash','-n',str(base/name)],check=True)
u=root/'infrastructure/systemd/phase1-original';u.mkdir(parents=True,exist_ok=False)
for name in ['ai-server.service','ai-backup.service']:shutil.copy2(before/name,u/name)
"""
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','nutec@172.19.5.250','python3 -c '+shlex.quote(remote)],input=json.dumps(payload).encode(),capture_output=True)
(ROOT/'docs/evidence/phase1-staging.json').write_bytes(r.stdout)
print(r.stdout.decode());print(r.stderr.decode());raise SystemExit(r.returncode)
