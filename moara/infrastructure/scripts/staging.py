"""Isolated real PostgreSQL/Redis/API acceptance environment, no published ports.

Credentials stay in a private directory; API reports contain only test outcomes.
This environment has no network route to production databases or inference.
"""
import json
import os
import secrets
import subprocess
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
PRIVATE=ROOT/'secrets/moara-staging'
LABEL='moara.environment=staging'
NETWORK='moara-staging-isolated'
NAMES=['moara-staging-pg','moara-staging-redis','moara-staging-api']

def command(args,stdin=None,timeout=90):
    result=subprocess.run(args,input=stdin,text=True,capture_output=True,timeout=timeout)
    if result.returncode:
        (PRIVATE/'last-error.log').write_text(result.stderr[-12000:]);os.chmod(PRIVATE/'last-error.log',0o600)
        raise RuntimeError('Isolated staging operation failed; private diagnostic retained')
    return result.stdout

def run(name,image,args=(),*,mounts=(),env=(),extra=()):
    argv=['docker','run','-d','--name',name,'--label',LABEL,'--network',NETWORK,
        '--memory','1g','--cpus','2','--pids-limit','128','--security-opt','no-new-privileges:true']
    for host,target in mounts:argv+=['--mount',f'type=bind,source={host},target={target},readonly']
    for value in env:argv+=['-e',value]
    return command(argv+list(extra)+[image]+list(args)).strip()

def wait(name,test,timeout=90):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        result=subprocess.run(['docker','exec',name,*test],capture_output=True)
        if result.returncode==0:return
        time.sleep(1)
    raise RuntimeError('Isolated staging readiness timed out: '+name)

def main():
    PRIVATE.mkdir(mode=0o700,parents=True,exist_ok=True);os.chmod(PRIVATE,0o700)
    for name in NAMES:
        found=subprocess.run(['docker','inspect',name],capture_output=True,text=True)
        if found.returncode==0:
            obj=json.loads(found.stdout)[0]
            if obj['Config'].get('Labels',{}).get('moara.environment')!='staging':raise RuntimeError('Unowned staging name collision')
            # Explicit replacement only of this isolated disposable environment.
            command(['docker','rm','-f',name])
    net=subprocess.run(['docker','network','inspect',NETWORK],capture_output=True,text=True)
    if net.returncode:
        command(['docker','network','create','--internal','--label',LABEL,NETWORK])
    elif json.loads(net.stdout)[0].get('Labels',{}).get('moara.environment')!='staging':raise RuntimeError('Unowned staging network')
    for name in ['postgres_password','moara_db_password','moara_migration_password','moara_session_key','moara_crypto_key',
        'moara_redis_password','moara_forward_jwt_secret','moara_llm_key','connector_hub_key','moara_metrics_key','admin_password']:
        (PRIVATE/name).write_text(secrets.token_hex(32));os.chmod(PRIVATE/name,0o644)
    redis_password=(PRIVATE/'moara_redis_password').read_text()
    (PRIVATE/'redis.conf').write_text('bind 0.0.0.0\nprotected-mode yes\nrequirepass '+redis_password+'\nsave ""\nappendonly no\nmaxmemory 128mb\nmaxmemory-policy noeviction\n')
    os.chmod(PRIVATE/'redis.conf',0o644)
    pgimage=command(['docker','inspect','-f','{{.Config.Image}}','ai-server-postgres-1']).strip()
    redisimage=command(['docker','inspect','-f','{{.Config.Image}}','ai-server-moara-redis-1']).strip()
    run(NAMES[0],pgimage,mounts=[(PRIVATE/'postgres_password','/run/secrets/pg')],
        env=['POSTGRES_PASSWORD_FILE=/run/secrets/pg','POSTGRES_DB=ai'])
    wait(NAMES[0],['pg_isready','-U','postgres','-d','ai'])
    sql='''CREATE ROLE moara_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE moara_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE SCHEMA moara AUTHORIZATION moara_migrator;
GRANT USAGE ON SCHEMA moara TO moara_app;
ALTER DEFAULT PRIVILEGES FOR ROLE moara_migrator IN SCHEMA moara GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO moara_app;
ALTER DEFAULT PRIVILEGES FOR ROLE moara_migrator IN SCHEMA moara GRANT USAGE,SELECT ON SEQUENCES TO moara_app;
ALTER DEFAULT PRIVILEGES FOR ROLE moara_migrator IN SCHEMA moara REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
'''
    command(['docker','exec','-i',NAMES[0],'psql','-U','postgres','-d','ai','-v','ON_ERROR_STOP=1'],sql)
    for role,filename in [('moara_app','moara_db_password'),('moara_migrator','moara_migration_password')]:
        password=(PRIVATE/filename).read_text()
        command(['docker','exec','-i',NAMES[0],'psql','-U','postgres','-d','ai','-v','ON_ERROR_STOP=1'],f'\\password {role}\n{password}\n{password}\n')
    command(['docker','run','--rm','--label',LABEL,'--network',NETWORK,'-e','MOARA_DB_HOST='+NAMES[0],
        '--mount',f'type=bind,source={PRIVATE}/moara_migration_password,target=/run/secrets/moara_migration_password,readonly','moara-core:1.0.0',
        'alembic','-c','/app/moara/gateway/alembic.ini','upgrade','head'])
    run(NAMES[1],redisimage,args=['redis-server','/run/secrets/redis.conf'],mounts=[(PRIVATE/'redis.conf','/run/secrets/redis.conf')],
        extra=['--network-alias','moara-redis'])
    runtime_secrets=['moara_db_password','moara_session_key','moara_crypto_key','moara_redis_password',
        'moara_forward_jwt_secret','moara_llm_key','connector_hub_key','moara_metrics_key','admin_password']
    run(NAMES[2],'moara-core:1.0.0',env=['MOARA_DB_HOST='+NAMES[0]],
        mounts=[(PRIVATE/name,'/run/secrets/'+name) for name in runtime_secrets],extra=['--read-only','--tmpfs','/tmp:size=64m'])
    wait(NAMES[2],['python','-c','import urllib.request;urllib.request.urlopen("http://localhost:8075/api/v1/ready",timeout=3)'])
    # Fixed fictitious local administrator; hashing happens in the isolated API.
    code='''import json,uuid,asyncio
from pathlib import Path
from moara.gateway.auth import PASSWORDS
from moara.gateway.database import Database
from moara.gateway.settings import Settings
async def main():
 db=Database(Settings.load());identifier=uuid.uuid5(uuid.NAMESPACE_URL,'moara-staging-admin')
 hashed=PASSWORDS.hash(Path('/run/secrets/admin_password').read_text())
 await db.execute("INSERT INTO moara.accounts(id,subject,name,email,auth_source,password_hash) VALUES(CAST(:id AS uuid),:subject,'Administrador de teste','admin@staging.invalid','local',:hash)",{'id':str(identifier),'subject':'local:'+str(identifier),'hash':hashed})
 await db.execute("INSERT INTO moara.account_roles(account_id,role_id) VALUES(CAST(:id AS uuid),'administrator')",{'id':str(identifier)})
 await db.dispose()
asyncio.run(main())
'''
    command(['docker','exec','-i',NAMES[2],'python','-'],code)
    report={'ready':True,'containers':NAMES,'network':NETWORK,'production_data_imported':False,'published_ports':False,
        'database':'isolated PostgreSQL','cache':'isolated Redis','identity':'versioned real application base',
        'inference_network_access':False}
    (ROOT/'docs/runtime/moara-staging.json').write_text(json.dumps(report,indent=2))
    print('MOARA_ISOLATED_STAGING_READY')

if __name__=='__main__':main()
