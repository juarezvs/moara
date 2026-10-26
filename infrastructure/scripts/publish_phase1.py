"""Publish only the approved operations fixes after verified preservation."""
import hashlib,json,os,shutil,stat,subprocess,sys
from pathlib import Path
os.umask(0o077)
stage=Path(sys.argv[1]).resolve()
if stage.parent!=Path('/home/nutec/moara-phase1'):raise ValueError('Unexpected staging directory')
root=Path('/home/nutec/ai-server');units=Path('/home/nutec/.config/systemd/user')
manifest=json.loads((root/'docs/runtime/moara-preservation-latest.json').read_text())
restore=json.loads((root/'docs/runtime/moara-preservation-restore.json').read_text())
assert manifest['verified'] and restore['verified'] and restore['configuration_hashes_matched']
assert manifest['file']==restore['backup']
assert json.loads((stage/'stack-smoke.json').read_text())['passed']
assert json.loads((stage/'tls-smoke.json').read_text())['certificate_verification']
assert 'Ran 5 tests' in (stage/'unit-tests.log').read_text() and 'OK' in (stage/'unit-tests.log').read_text()
existing=['moara/infrastructure/scripts/preservation.py','infrastructure/scripts/backup.sh','infrastructure/scripts/deploy.sh']
for name in existing:
 assert (root/name).read_bytes()==(stage/'before'/name).read_bytes(),'Production script changed: '+name
for name in ['ai-server.service','ai-backup.service']:
 assert (units/name).read_bytes()==(stage/'before'/name).read_bytes(),'Unit changed: '+name
new=['moara/infrastructure/scripts/config_snapshot.py','infrastructure/scripts/start-services.sh']
for name in new:assert not (root/name).exists(),'New target already exists: '+name
report={'backup':manifest['file'],'files':{},'host_rebooted':False}
def install(source,target):
 content=source.read_bytes()
 target.parent.mkdir(parents=True,exist_ok=True)
 mode=stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o600
 temp=target.with_name(target.name+'.phase1-new')
 with temp.open('xb') as stream:stream.write(content)
 temp.chmod(mode);temp.replace(target)
 report['files'][str(target)]=hashlib.sha256(content).hexdigest()
for name in existing+new:install(stage/name,root/name)
for name in ['ai-server.service','ai-backup.service']:
 install(stage/'infrastructure/systemd'/name,root/'infrastructure/systemd'/name)
 install(stage/'infrastructure/systemd'/name,units/name)
subprocess.run(['systemctl','--user','daemon-reload'],check=True)
subprocess.run(['systemctl','--user','start','--no-block','ai-server.service'],check=True)
(stage/'publication.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
