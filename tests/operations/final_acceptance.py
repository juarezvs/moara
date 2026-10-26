import hashlib,json,stat,subprocess,sys
from pathlib import Path
stage=Path(sys.argv[1]);root=Path('/home/nutec/ai-server')
def run(args):return subprocess.run(args,check=True,capture_output=True,text=True).stdout.strip()
def service(name):
 text=run(['systemctl','--user','show',name,'-p','ActiveState','-p','SubState','-p','Result','-p','ExecMainStatus'])
 return dict(line.split('=',1) for line in text.splitlines() if '=' in line)
server=service('ai-server.service');backup=service('ai-backup.service')
assert server['ActiveState']=='active' and server['Result']=='success' and server['ExecMainStatus']=='0'
assert backup['Result']=='success' and backup['ExecMainStatus']=='0' and backup['ActiveState']=='inactive'
assert run(['systemctl','--user','is-active','ai-backup.timer'])=='active'
before={row.split()[0]:row.split()[1] for row in (stage/'containers-before.txt').read_text().splitlines()}
after={row.split()[0]:row.split()[1] for row in run(['docker','ps','--no-trunc','--format','{{.Names}} {{.ID}}']).splitlines()}
assert before==after,'Production containers changed'
rows=json.loads(run(['docker','inspect',*after.values()]))
health={row['Name'].lstrip('/'):row['State'].get('Health',{}).get('Status','no_healthcheck') for row in rows}
assert all(state in ['healthy','no_healthcheck'] for state in health.values())
publication=json.loads((stage/'publication.json').read_text())
for filename,digest in publication['files'].items():assert hashlib.sha256(Path(filename).read_bytes()).hexdigest()==digest
latest=json.loads((root/'docs/runtime/moara-preservation-latest.json').read_text())
restore=json.loads((root/'docs/runtime/moara-preservation-restore.json').read_text())
assert latest['verified'] and restore['verified'] and latest['file']==restore['backup']
assert restore['configuration_hashes_matched']
p=root/'secrets/secp_rbac_config.json';protected=p.stat()
assert stat.S_IMODE(protected.st_mode)==0o400 and protected.st_uid==110000 and protected.st_gid==110000
assert not run(['docker','ps','-aq','--filter','label=moara.phase1.test'])
assert not run(['docker','volume','ls','-q','--filter','label=moara.phase1.test'])
report={'server_unit':server,'backup_unit':backup,'backup_timer':'active','production_container_ids_unchanged':True,
 'containers':len(after),'container_health':health,'publication_hashes_matched':True,'protected_file_permissions_unchanged':True,
 'fixture_resources_removed':True,'backup':latest,'restore':restore}
(stage/'final-acceptance.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
