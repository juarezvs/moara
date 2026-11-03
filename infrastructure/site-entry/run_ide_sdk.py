import pathlib,subprocess,json,importlib.util,sys
ROOT=pathlib.Path('/home/nutec/ai-server');WORK=ROOT/'infrastructure/site-entry'
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
stage='--stage' in sys.argv;name='moara-ide-sdk-'+('stage' if stage else 'public');artifacts=WORK/('ide-sdk-stage' if stage else 'ide-sdk-public');artifacts.mkdir(exist_ok=True);artifacts.chmod(0o777)
base='http://'+(ROOT/'tmp/ide-core-name.txt').read_text().strip()+':8075' if stage else 'https://moara.am.trf1.gov.br/moara'
for filename in ['ide-sdk.json','ide-generated.py']:
 path=artifacts/filename
 if path.exists():path.unlink()
args=['docker','run','--rm','-i','--network',('ai-server_frontend' if stage else 'ai-server_download'),'--read-only','--tmpfs','/tmp:size=64m','--memory','512m','--cpus','1','--cap-drop','ALL','-e','PYTHONPATH=/sdk','-v',str(ROOT/'tmp/ide-sdk')+':/sdk:ro','-v',str(WORK/'ide_sdk_test.py')+':/test.py:ro','-v',str(artifacts)+':/artifacts','-v',str(ROOT/'moara/web/public/integrations/moara-domain-root-ca.crt')+':/ca.crt:ro','--entrypoint','python','moara-core:ide-20261030','/test.py']
r=subprocess.run(args,input=json.dumps({'token':m.admin_session(),'base':base})+'\n',text=True,capture_output=True,timeout=600)
report=artifacts/'ide-sdk.json'
if report.exists():
 data=json.loads(report.read_text());session_hash=data.pop('test_session_sha256',None)
 code="""import asyncio,sys,json
from moara.gateway.database import Database
from moara.gateway.settings import Settings
async def main():
 data=json.load(sys.stdin);db=Database(Settings.load())
 if data['session']:await db.execute('UPDATE moara.sessions SET revoked_at=now() WHERE token_hash=:hash',{'hash':data['session']})
 for key in data['keys']:await db.execute('UPDATE moara.api_keys SET revoked_at=COALESCE(revoked_at,now()) WHERE id=CAST(:id AS uuid)',{'id':key})
 await db.dispose()
asyncio.run(main())"""
 subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=json.dumps({'session':session_hash,'keys':data['test_key_ids']}),text=True,capture_output=True,check=True)
 data['test_credentials_revoked']=True;report.unlink();report.write_text(json.dumps(data,indent=2));(ROOT/'docs/runtime'/('ide-sdk-stage.json' if stage else 'ide-sdk-public.json')).write_text(json.dumps(data,indent=2))
if r.returncode==0:
 test="import runpy;f=runpy.run_path('/fixture.py')['normalize_name'];assert f('  MARIA   SILVA  ')== 'maria silva';assert f(' A'+chr(9)+'B'+chr(10)+'C ')== 'a b c';assert f('')=='';assert f('  ') == '';print('GENERATED_CODE_TESTS_PASSED')"
 checked=subprocess.run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=32m','--memory','128m','--cpus','1','--pids-limit','32','--cap-drop','ALL','-v',str(artifacts/'ide-generated.py')+':/fixture.py:ro','--entrypoint','python','moara-core:ide-20261030','-c',test],capture_output=True,text=True)
 if checked.returncode:raise RuntimeError('Generated software fixture did not pass isolated functional checks')
 data['checks']['generated_code_functional_tests']=True
 (ROOT/'docs/runtime'/('ide-sdk-stage.json' if stage else 'ide-sdk-public.json')).write_text(json.dumps(data,indent=2))
 print(checked.stdout)
print(r.stdout)
if r.returncode:print(r.stderr[-1800:])
raise SystemExit(r.returncode)
