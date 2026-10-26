"""Disposable databases only. No production source address is accepted by this script."""
import json
import secrets
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
images={'pg':'postgres:17','mysql':'mysql:8.4','mariadb':'mariadb:11.4','mssql':'mcr.microsoft.com/mssql/server:2022-latest',
    'oracle':'gvenzl/oracle-free:23-slim-faststart','mongodb':'mongo:7.0'}
for kind,image in images.items():
    subprocess.run(['docker','pull',image],check=True,stdout=subprocess.DEVNULL)
    digest=json.loads(subprocess.check_output(['docker','image','inspect',image]))[0]['RepoDigests'][0]
    images[kind]=digest;print('FIXTURE_IMAGE_READY',kind,flush=True)
folder=ROOT/'secrets';credentials=folder/'connector_fixture_credentials.json'
if credentials.exists():data=json.loads(credentials.read_text())
else:
    data={'admin_password':'F1!'+secrets.token_hex(20),'reader_password':'R2!'+secrets.token_hex(20),'token':secrets.token_urlsafe(32)}
    credentials.write_text(json.dumps(data));credentials.chmod(0o600)
for name,value in data.items():
    path=folder/('fixture_'+name);path.write_text(value);path.chmod(0o644)
services={}
for index,(kind,image) in enumerate(images.items()):
    env={};command=None;entrypoint=None
    if kind=='pg':env={'POSTGRES_PASSWORD_FILE':'/run/secrets/admin_password'}
    elif kind=='mysql':env={'MYSQL_ROOT_PASSWORD_FILE':'/run/secrets/admin_password'}
    elif kind=='mariadb':env={'MARIADB_ROOT_PASSWORD_FILE':'/run/secrets/admin_password'}
    elif kind=='mongodb':env={'MONGO_INITDB_ROOT_USERNAME':'root','MONGO_INITDB_ROOT_PASSWORD_FILE':'/run/secrets/admin_password'}
    elif kind=='oracle':env={'ORACLE_PASSWORD_FILE':'/run/secrets/admin_password'}
    elif kind=='mssql':
        env={'ACCEPT_EULA':'Y','MSSQL_PID':'Developer','MSSQL_MEMORY_LIMIT_MB':'6144'}
        command=['bash','-c','export MSSQL_SA_PASSWORD="$$(cat /run/secrets/admin_password)"; exec taskset -c 0-3 /opt/mssql/bin/sqlservr']
    services[kind]={'image':image,'container_name':'cc-fixture-'+kind,'profiles':['fixtures'],
        'labels':{'curumim.fixtures':'true'},'environment':env,
        'secrets':['admin_password'],'networks':{'outbound':{'ipv4_address':'10.91.240.'+str(100+index)}},
        'mem_limit':'5g' if kind=='oracle' else '8g' if kind=='mssql' else '1g','cpus':2,'pids_limit':256,
        'logging':{'driver':'json-file','options':{'max-size':'2m','max-file':'2'}}}
    if command:services[kind]['command']=command
services['rest']={'image':'ai-gateway:1.0.0','container_name':'cc-fixture-rest','profiles':['fixtures'],'labels':{'curumim.fixtures':'true'},
    'command':['uvicorn','fixture-rest:app','--host','0.0.0.0','--port','8080','--no-access-log'],
    'volumes':['../tests/fixture-rest.py:/app/fixture-rest.py:ro'],'secrets':['token'],
    'networks':{'outbound':{'ipv4_address':'10.91.240.106'}},'mem_limit':'256m','cpus':1,'read_only':True,'cap_drop':['ALL']}
compose={'services':services,'networks':{'outbound':{'external':True,'name':'ai-server_connector_outbound'}},
    'secrets':{'admin_password':{'file':'../../secrets/fixture_admin_password'},'token':{'file':'../../secrets/fixture_token'}}}
(ROOT/'connectors/deployment/fixtures.yml').write_text(json.dumps(compose,indent=2))
(ROOT/'docs/runtime/connector-fixture-images.json').write_text(json.dumps(images,indent=2))
print('FIXTURE_IMAGES_AND_SECRETS_READY',flush=True)
