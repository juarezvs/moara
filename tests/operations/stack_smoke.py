"""Exercise the real startup wrapper with synthetic, isolated containers."""
import json,os,secrets,shlex,shutil,subprocess,sys
from pathlib import Path
os.umask(0o077)
base=Path(sys.argv[1]).resolve()
root=Path('/home/nutec/ai-server')
env=dict(line.split('=',1) for line in (root/'infrastructure/.env').read_text().splitlines() if '=' in line)
nonce=secrets.token_hex(6);project='moara-phase1-'+nonce
fixture=base/'fixture';fixture.mkdir()
for name in ['infrastructure/scripts','moara/infrastructure/scripts','backups']:(fixture/name).mkdir(parents=True,exist_ok=True)
(fixture/'password').write_text(secrets.token_hex(32))
shutil.copy2(base/'infrastructure/scripts/start-services.sh',fixture/'infrastructure/scripts/start-services.sh')
label={'moara.phase1.test':nonce}
config={'services':{
 'db':{'image':env['POSTGRES_IMAGE'],'network_mode':'none','mem_limit':'1g','cpus':1,'labels':label,
 'environment':{'POSTGRES_PASSWORD_FILE':'/run/password','POSTGRES_DB':'fixture'},
 'volumes':[str(fixture/'password')+':/run/password:ro','pg:/var/lib/postgresql/data'],
 'healthcheck':{'test':['CMD-SHELL','pg_isready -U postgres -d fixture'],'interval':'1s','timeout':'2s','retries':60}},
 'probe':{'image':env['PYTHON_IMAGE'],'network_mode':'none','mem_limit':'128m','cpus':1,'labels':label,
 'read_only':True,'cap_drop':['ALL'],'security_opt':['no-new-privileges:true'],
 'depends_on':{'db':{'condition':'service_healthy'}},'volumes':['marker:/marker'],
 'command':['python','-c',"from pathlib import Path; import time; p=Path('/marker/proof'); p.touch(exist_ok=True); time.sleep(3600)"],
 'healthcheck':{'test':['CMD','python','-c',"from pathlib import Path; assert Path('/marker/proof').exists()"],'interval':'1s','timeout':'2s','retries':60}}},
 'volumes':{'pg':{'labels':label},'marker':{'labels':label}}}
(fixture/'compose.json').write_text(json.dumps(config))
command=['docker','compose','-p',project,'-f',str(fixture/'compose.json')]
(fixture/'moara/infrastructure/scripts/compose.sh').write_text('#!/bin/sh\nexec '+shlex.join(command)+' "$@"\n')
def run(args):return subprocess.run(args,capture_output=True,text=True,check=True).stdout.strip()
def cid(name):return run(command+['ps','-a','-q',name])
result={'project':project,'network':'none','synthetic_data':True,'passed':False}
try:
 run(['bash',str(fixture/'infrastructure/scripts/start-services.sh')])
 first={name:cid(name) for name in ['db','probe']}
 run(['docker','exec',first['db'],'psql','-U','postgres','-d','fixture','-v','ON_ERROR_STOP=1','-c',"CREATE TABLE proof(id integer PRIMARY KEY); INSERT INTO proof VALUES (42);"])
 run(command+['stop'])
 run(['bash',str(fixture/'infrastructure/scripts/start-services.sh')])
 second={name:cid(name) for name in ['db','probe']}
 assert first==second,'Startup recreated a container'
 assert run(['docker','exec',second['db'],'psql','-U','postgres','-d','fixture','-Atc','SELECT id FROM proof'])=='42'
 run(['docker','exec',second['probe'],'python','-c',"from pathlib import Path; assert Path('/marker/proof').is_file()"])
 result.update(passed=True,postgres_persistence=True,volume_persistence=True,containers_not_recreated=True,dependency_health_wait=True)
finally:
 # Remove only the fixtures whose unique labels match this run.
 for service in ['probe','db']:
  container=cid(service)
  if container:
   data=json.loads(run(['docker','inspect',container]))[0]
   assert data['Config']['Labels'].get('moara.phase1.test')==nonce
   run(['docker','rm','-f',container])
 for suffix in ['pg','marker']:
  volume=project+'_'+suffix
  exists=subprocess.run(['docker','volume','inspect',volume],capture_output=True,text=True)
  if exists.returncode==0:
   data=json.loads(exists.stdout)[0];assert data['Labels'].get('moara.phase1.test')==nonce
   run(['docker','volume','rm',volume])
 (base/'stack-smoke.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
