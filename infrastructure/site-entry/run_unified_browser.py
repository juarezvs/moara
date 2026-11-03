import pathlib,subprocess,json,importlib.util,ssl,socket,hashlib,base64,shutil,time,sys
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
ROOT=pathlib.Path('/home/nutec/ai-server');WORK=ROOT/'infrastructure/site-entry';stage='--stage' in sys.argv
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ctx=ssl.create_default_context();ctx.load_verify_locations(cafile=str(ROOT/'docs/runtime/ai-root-ca.crt'));ctx.load_verify_locations(cafile=str(ROOT/'docs/runtime/moara-domain-root-ca.crt'))
with socket.create_connection(('172.19.5.250',443),timeout=10) as raw:
 with ctx.wrap_socket(raw,server_hostname='moara.am.trf1.gov.br') as tls:certificate=x509.load_der_x509_certificate(tls.getpeercert(binary_form=True))
spki=base64.b64encode(hashlib.sha256(certificate.public_key().public_bytes(Encoding.DER,PublicFormat.SubjectPublicKeyInfo)).digest()).decode()
token=m.admin_session();stamp=str(time.time_ns());title='Unificacao sintetica '+stamp
fixture_code=r'''
import sys,json,uuid,time,httpx
from moara.gateway.settings import Settings
token,title=json.load(sys.stdin);root=Settings.load().legacy_webui;u,a,b=[str(uuid.uuid4()) for _ in range(3)]
messages={u:{'id':u,'role':'user','content':'Registro fictício para validar a unificação da Moara.','parentId':None,'childrenIds':[a,b],'timestamp':int(time.time())},a:{'id':a,'role':'assistant','content':'Resposta histórica selecionada: verificar o relatório no próximo expediente.','parentId':u,'childrenIds':[],'done':True,'timestamp':int(time.time())},b:{'id':b,'role':'assistant','content':'VERSÃO NÃO SELECIONADA: não utilizar.','parentId':u,'childrenIds':[],'done':True,'timestamp':int(time.time())}}
with httpx.Client(timeout=20,trust_env=False) as c:
 r=c.post(root+'/api/v1/chats/new',headers={'Authorization':'Bearer '+token},json={'chat':{'title':title,'models':['moara-auto'],'history':{'currentId':a,'messages':messages},'messages':[messages[u],messages[a]],'files':[{'id':'SYNTHETIC_ATTACHMENT','name':'anexo-sintetico.txt'}]}})
 if r.status_code not in (200,201):raise RuntimeError('Synthetic previous chat creation failed: '+str(r.status_code))
 print(json.dumps({'id':r.json()['id'],'title':title}))
'''
r=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',fixture_code],input=json.dumps([token,title]),text=True,capture_output=True,check=True)
old=json.loads(r.stdout);proxy=(ROOT/'tmp/unified-proxy-name.txt').read_text().strip() if stage else ''
tested_target=(ROOT/'tmp/unified-core-name.txt').read_text().strip() if stage else 'ai-server-moara-gateway-1'
tested_image_id=subprocess.check_output(['docker','inspect',tested_target,'--format','{{.Image}}'],text=True).strip()
cfg=json.loads(subprocess.check_output(['sh',str(ROOT/'moara/infrastructure/scripts/compose.sh'),'config','--format','json']))
renderer=json.loads(subprocess.check_output(['docker','inspect','ai-server-studio-renderer-1']))[0]
name='moara-unified-browser-'+('stage-' if stage else 'public-')+stamp;artifacts=WORK/('unified-output-'+stamp);artifacts.mkdir();artifacts.chmod(0o777)
args=['docker','create','-i','--name',name,'--network','ai-server_frontend','--read-only','--tmpfs','/tmp:size=1g,mode=1777','--shm-size','512m','--memory','2g','--cpus','2','--pids-limit','512','-e','HOME=/tmp','-v',str(WORK/('chat_background_ui_test.py' if '--chat-background' in sys.argv else 'chat_reading_ui_test.py' if '--scroll-reading' in sys.argv else 'chat_scroll_ui_test.py' if '--chat-scroll' in sys.argv else 'chat_reading_ui_test.py' if '--institutional-reading' in sys.argv else 'institutional_ui_test.py' if '--institutional-ui' in sys.argv else 'chat_reading_ui_test.py' if '--chat-reading' in sys.argv else 'legal_metadata_ui_test.py' if '--legal-metadata' in sys.argv else 'stf_catalog_ui_test.py' if '--stf-catalog' in sys.argv else 'careers_ui_test.py' if '--careers' in sys.argv else 'citations_ui_test.py' if '--citations' in sys.argv else 'unified_ui_test.py'))+':/tmp/ui_test.py:ro','-v',str(artifacts)+':/artifacts']
for option in cfg['services']['studio-renderer'].get('security_opt',[]):
 if option.startswith('seccomp=') and not option.startswith('seccomp=/'):option='seccomp='+str((ROOT/'infrastructure'/option.split('=',1)[1]).resolve())
 args+=['--security-opt',option]
args+=['--entrypoint','python3',renderer['Image'],'-u','/tmp/ui_test.py'];subprocess.run(args,check=True,capture_output=True)
subprocess.run(['docker','network','connect','ai-server_download',name],check=True,capture_output=True)
try:
 r=subprocess.run(['docker','start','-a','-i',name],input=json.dumps({'token':token,'spki':spki,'proxy':proxy,'old_title':old['title'],'old_id':old['id']})+'\n',text=True,capture_output=True,timeout=600)
 print(r.stdout)
 if r.returncode:print('BROWSER_CHECK_FAILED: inspect redacted logs; headers are suppressed.')
finally:
 report_path=artifacts/'unified-ui.json';report=json.loads(report_path.read_text()) if report_path.exists() else {'checks':{}}
 session_hash=report.pop('test_session_sha256',None)
 cleanup=r'''
import sys,json,asyncio,httpx
from moara.gateway.settings import Settings
from moara.gateway.database import Database
async def main():
 data=json.load(sys.stdin);s=Settings.load();db=Database(s)
 if data['session']:await db.execute('UPDATE moara.sessions SET revoked_at=now() WHERE token_hash=:hash',{'hash':data['session']})
 for identifier in data.get('accounts',[]):
  row=await db.execute("SELECT id FROM moara.accounts WHERE id=CAST(:id AS uuid) AND auth_source='local' AND email LIKE 'rbac-qa-%@example.invalid' AND name LIKE 'RBAC QA %'",{'id':identifier},one=True)
  assert row,'Unowned RBAC fixture'
  await db.execute('UPDATE moara.accounts SET active=false WHERE id=CAST(:id AS uuid)',{'id':identifier})
  await db.execute('UPDATE moara.sessions SET revoked_at=now() WHERE account_id=CAST(:id AS uuid)',{'id':identifier})
  await db.execute('UPDATE moara.chats SET archived=true WHERE account_id=CAST(:id AS uuid)',{'id':identifier})
 await db.dispose()
 async with httpx.AsyncClient(trust_env=False,timeout=20) as c:
  r=await c.post(s.legacy_webui+'/api/v1/chats/'+data['old']+'/archive',headers={'Authorization':'Bearer '+data['token']});assert r.status_code==200
  print(json.dumps({'native_test_session_revoked':bool(data['session']),'synthetic_previous_chat_archived':True}))
asyncio.run(main())
'''
 cleaned=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',cleanup],input=json.dumps({'session':session_hash,'old':old['id'],'token':token,'accounts':report.get('created_rbac_accounts',[])}),text=True,capture_output=True,check=True)
 report.update(json.loads(cleaned.stdout));report['test_container']=name;report['old_fixture_id']=old['id']
 target=(ROOT/'tmp/unified-core-name.txt').read_text().strip() if stage else 'ai-server-moara-gateway-1'
 report['tested_image_id']=tested_image_id
 (ROOT/'docs/runtime'/(('chat-background-ui-stage.json' if stage else 'chat-background-ui-public.json') if '--chat-background' in sys.argv else ('chat-scroll-reading-stage.json' if stage else 'chat-scroll-reading-public.json') if '--scroll-reading' in sys.argv else ('chat-scroll-ui-stage.json' if stage else 'chat-scroll-ui-public.json') if '--chat-scroll' in sys.argv else ('institutional-reading-ui-stage.json' if stage else 'institutional-reading-ui-public.json') if '--institutional-reading' in sys.argv else ('institutional-ui-stage.json' if stage else 'institutional-ui-public.json') if '--institutional-ui' in sys.argv else ('chat-reading-ui-stage.json' if stage else 'chat-reading-ui-public.json') if '--chat-reading' in sys.argv else ('legal-metadata-ui-stage.json' if stage else 'legal-metadata-ui-public.json') if '--legal-metadata' in sys.argv else ('stf-catalog-ui-stage.json' if stage else 'stf-catalog-ui-public.json') if '--stf-catalog' in sys.argv else ('careers-ui-stage.json' if stage else 'careers-ui-public.json') if '--careers' in sys.argv else ('citations-ui-stage.json' if stage else 'citations-ui-public.json') if '--citations' in sys.argv else ('unified-ui-stage.json' if stage else 'unified-ui-public.json'))).write_text(json.dumps(report,indent=2))
 for file in ['unified-desktop.png','unified-mobile.png','unified-dark.png']:
  if (artifacts/file).exists():shutil.copyfile(artifacts/file,ROOT/'docs/runtime'/file)
raise SystemExit(r.returncode)
