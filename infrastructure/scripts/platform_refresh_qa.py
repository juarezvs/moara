import json,subprocess
from pathlib import Path
ROOT=Path('/home/nutec/ai-server');STAGE=Path('/home/nutec/moara-platform-20261026-r2')
p=subprocess.run(['docker','build','-t','moara-core:platform-20261026-r2','-f',str(STAGE/'moara/gateway/Dockerfile'),str(STAGE)],capture_output=True,timeout=600)
if p.returncode:print(p.stderr.decode()[-4000:]);raise SystemExit(1)
source=(ROOT/'moara/infrastructure/scripts/staging.py').read_text().replace("ROOT=Path(__file__).resolve().parents[3]","ROOT=Path('/home/nutec/ai-server')").replace('secrets/moara-staging','secrets/moara-platform-qa').replace('moara-staging','moara-platform-qa')
ns={'__name__':'fixture_refresh'};exec(source,ns)
name=ns['NAMES'][2];obj=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
if obj['Config'].get('Labels',{}).get('moara.environment')!='staging':raise RuntimeError('unowned fixture')
subprocess.run(['docker','rm','-f',name],capture_output=True,check=True)
runtime=['moara_db_password','moara_session_key','moara_crypto_key','moara_redis_password','moara_forward_jwt_secret','moara_llm_key','connector_hub_key','moara_metrics_key','admin_password']
ns['run'](name,'moara-core:platform-20261026-r2',env=['MOARA_DB_HOST='+ns['NAMES'][0],'MOARA_SANDBOX_READY=true'],
 mounts=[(ns['PRIVATE']/s,'/run/secrets/'+s) for s in runtime],extra=['--read-only','--tmpfs','/tmp:size=128m'])
ns['wait'](name,['python','-c','import urllib.request;urllib.request.urlopen("http://localhost:8075/api/v1/ready",timeout=3)'])
print('CANDIDATE_REFRESHED_WITHOUT_DATABASE_RESET')
