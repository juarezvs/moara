"""Prepare only new Moara credentials, isolated DB roles and Redis storage.

Passwords use psql's client-side SCRAM password command, never SQL literals in
logs or process arguments. Existing roles, passwords and volumes are preserved.
"""
import json
import os
import re
import secrets
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
os.umask(0o077)
directory=ROOT/'secrets';directory.mkdir(mode=0o700,exist_ok=True);directory.chmod(0o700)
report=json.loads((ROOT/'docs/runtime/moara-preservation-restore.json').read_text())
assert report['verified'] and report['production_modified'] is False,'A verified preservation is required before initial provisioning'

def run(args,input=None):
    result=subprocess.run(args,input=input,text=True,capture_output=True)
    if result.returncode:
        (directory/'moara-provisioning-error.log').write_text(result.stderr)
        raise RuntimeError('Moara provisioning failed; diagnostic kept in protected secrets directory')
    return result.stdout.strip()

names=['moara_session_key','moara_crypto_key','moara_redis_password','moara_forward_jwt_secret',
    'moara_db_password','moara_migration_password','moara_worker_password']
for name in names:
    path=directory/name
    if not path.exists():path.write_text(secrets.token_hex(32))
    if not re.fullmatch(r'[0-9a-f]{64}',path.read_text().strip()):raise ValueError('Unexpected protected credential format')
    path.chmod(0o644)  # Parent 0700; rootless Docker bind-mounts files for service UIDs.

def sql(query):return run(['docker','exec','-i','ai-server-postgres-1','psql','-U','postgres','-d','ai','-qAt','-v','ON_ERROR_STOP=1'],query+'\n')
for role,key in [('moara_migrator','moara_migration_password'),('moara_app','moara_db_password'),('moara_worker','moara_worker_password')]:
    exists=sql("SELECT count(*) FROM pg_roles WHERE rolname='"+role+"'")=='1'
    if not exists:
        sql('CREATE ROLE '+role+' LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS')
        password=(directory/key).read_text().strip()
        run(['docker','exec','-i','ai-server-postgres-1','psql','-U','postgres','-d','ai','-v','ON_ERROR_STOP=1','-c','\\password '+role],password+'\n'+password+'\n')
    sql('GRANT CONNECT ON DATABASE ai TO '+role)
sql('''CREATE SCHEMA IF NOT EXISTS moara AUTHORIZATION moara_migrator;
REVOKE ALL ON SCHEMA moara FROM PUBLIC;
GRANT USAGE ON SCHEMA moara TO moara_app,moara_worker;
ALTER DEFAULT PRIVILEGES FOR ROLE moara_migrator IN SCHEMA moara GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO moara_app;
ALTER DEFAULT PRIVILEGES FOR ROLE moara_migrator IN SCHEMA moara GRANT USAGE,SELECT ON SEQUENCES TO moara_app;
ALTER DEFAULT PRIVILEGES FOR ROLE moara_migrator IN SCHEMA moara REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;''')

redis_conf=directory/'moara_redis_config'
if not redis_conf.exists():
    redis_conf.write_text('''bind 0.0.0.0
protected-mode yes
port 6379
dir /data
appendonly yes
appendfsync everysec
save ""
maxmemory 256mb
maxmemory-policy noeviction
loglevel warning
requirepass '''+(directory/'moara_redis_password').read_text().strip()+'\n')
    redis_conf.chmod(0o644)

volume='ai-server_moara_redis'
result=subprocess.run(['docker','volume','inspect',volume],capture_output=True,text=True)
if result.returncode:
    run(['docker','volume','create','--label','moara.owner=platform','--label','com.docker.compose.project=ai-server',
        '--label','com.docker.compose.volume=moara_redis',volume])
    env=dict(line.split('=',1) for line in (ROOT/'infrastructure/.env').read_text().splitlines() if '=' in line)
    run(['docker','run','--rm','--pull=never','--network','none','--read-only','--mount','type=volume,src='+volume+',dst=/data',
        env['PYTHON_IMAGE'],'python','-c',"import os;os.chown('/data',10001,10001)"])
for image in ['ai-gateway:runtime-20261020']:
    if subprocess.run(['docker','image','inspect',image],capture_output=True).returncode:run(['docker','tag','ai-gateway:1.0.0',image])
(ROOT/'docs/runtime/moara-host-telemetry.json').touch(exist_ok=True)
print('MOARA_NEW_SECRETS_AND_DATABASE_ROLES_PREPARED; existing accounts and databases preserved')
