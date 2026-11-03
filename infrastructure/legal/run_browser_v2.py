import pathlib,subprocess,json,importlib.util,ssl,socket,hashlib,base64,shutil
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
ROOT=pathlib.Path('/home/nutec/ai-server');WORK=ROOT/'infrastructure/legal'
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ctx=ssl.create_default_context();ctx.load_verify_locations(cafile=str(ROOT/'docs/runtime/ai-root-ca.crt'))
ctx.load_verify_locations(cafile=str(ROOT/'docs/runtime/moara-domain-root-ca.crt'))
with socket.create_connection(('172.19.5.250',443),timeout=10) as raw:
 with ctx.wrap_socket(raw,server_hostname='moara.am.trf1.gov.br') as tls:certificate=x509.load_der_x509_certificate(tls.getpeercert(binary_form=True))
spki=base64.b64encode(hashlib.sha256(certificate.public_key().public_bytes(Encoding.DER,PublicFormat.SubjectPublicKeyInfo)).digest()).decode()
cfg=json.loads(subprocess.check_output(['sh',str(ROOT/'moara/infrastructure/scripts/compose.sh'),'config','--format','json']))
renderer=json.loads(subprocess.check_output(['docker','inspect','ai-server-studio-renderer-1']))[0]
name='moara-legal-v2-browser-'+('stage' if '--stage' in __import__('sys').argv else 'public')
if subprocess.run(['docker','inspect',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
 subprocess.run(['docker','rename',name,name+'-previous-'+str(__import__('time').time_ns())],check=True)
args=['docker','create','-i','--name',name,'--network','ai-server_frontend','--read-only','--tmpfs','/tmp:size=1g,mode=1777','--shm-size','512m','--memory','2g','--cpus','2','--pids-limit','512','-e','HOME=/tmp','-v',str(WORK/'browser_v2.py')+':/tmp/ui_test.py:ro']
artifacts=WORK/'v2-ui-output';artifacts.mkdir(exist_ok=True);artifacts.chmod(0o777)
args+=['-v',str(artifacts)+':/artifacts']
for option in cfg['services']['studio-renderer'].get('security_opt',[]):
 if option.startswith('seccomp=') and not option.startswith('seccomp=/'):
  option='seccomp='+str((ROOT/'infrastructure'/option.split('=',1)[1]).resolve())
 args+=['--security-opt',option]
args+=['--entrypoint','python3',renderer['Image'],'-u','/tmp/ui_test.py']
subprocess.run(args,check=True,capture_output=True)
subprocess.run(['docker','network','connect','ai-server_download','moara-legal-v2-browser-'+('stage' if '--stage' in __import__('sys').argv else 'public')+''],check=True)
previous_path=ROOT/'docs/runtime/legal-sources-v2-ui.json'
previous=json.loads(previous_path.read_text()) if previous_path.exists() else {}
previous_chats=[] if previous.get('checks',{}).get('synthetic_chat_archived') else previous.get('created_chats',[])
r=subprocess.run(['docker','start','-a','-i','moara-legal-v2-browser-'+('stage' if '--stage' in __import__('sys').argv else 'public')+''],input=json.dumps({'token':m.admin_session(),'spki':spki,'candidate':json.loads((ROOT/'tmp/legal-v2-stage.json').read_text())['core'] if '--stage' in __import__('sys').argv else '', 'previous_chats':previous_chats,'today':__import__('datetime').datetime.now(__import__('zoneinfo').ZoneInfo('America/Manaus')).date().isoformat()})+'\n',text=True,capture_output=True,timeout=600)
print(r.stdout,flush=True)
if r.returncode:print('BROWSER_CHECK_FAILED: inspect protected container logs; request headers suppressed.',flush=True)
for name in ['legal-sources-v2-ui.json']:
 if (artifacts/name).exists():shutil.copyfile(artifacts/name,ROOT/'docs/runtime'/name)
# Preserve the stopped synthetic test container.
report_path=ROOT/'docs/runtime/legal-sources-v2-ui.json'
if report_path.exists():
 report=json.loads(report_path.read_text());session_hash=report.pop('test_session_sha256',None)
 if session_hash:
  code="""import asyncio,sys
from moara.gateway.database import Database
from moara.gateway.settings import Settings
async def main():
 db=Database(Settings.load());await db.execute('UPDATE moara.sessions SET revoked_at=now() WHERE token_hash=:hash',{'hash':sys.stdin.read().strip()});await db.dispose()
asyncio.run(main())
"""
  subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=session_hash,text=True,check=True,capture_output=True)
  report['native_test_session_revoked']=True;report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
raise SystemExit(r.returncode)
