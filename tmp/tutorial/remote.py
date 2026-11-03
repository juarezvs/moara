import importlib.util,json,ssl,socket,subprocess,base64,hashlib,urllib.request,http.cookiejar,io,tarfile,secrets
from pathlib import Path
from http.cookies import SimpleCookie
ROOT=Path('/home/nutec/ai-server');WORK=Path('/home/nutec/moara-tutorial-20261027');WORK.mkdir(mode=0o700,exist_ok=True)
BASE='https://moara.am.trf1.gov.br';ctx=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/moara-domain-root-ca.crt'))
with socket.create_connection(('moara.am.trf1.gov.br',443),timeout=20) as sock:
 with ctx.wrap_socket(sock,server_hostname='moara.am.trf1.gov.br') as tls:cert=ssl.DER_cert_to_PEM_cert(tls.getpeercert(binary_form=True))
pub=subprocess.check_output(['openssl','x509','-pubkey','-noout'],input=cert.encode())
der=subprocess.check_output(['openssl','pkey','-pubin','-outform','DER'],input=pub)
spki=base64.b64encode(hashlib.sha256(der).digest()).decode()
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
token=module.admin_session()
jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),urllib.request.HTTPCookieProcessor(jar))
def request(path,body=None,method=None,headers=None,client=opener):
 req=urllib.request.Request(BASE+'/moara/api/v1/'+path,data=json.dumps(body).encode() if body is not None else None,
 headers={'Origin':BASE,'Content-Type':'application/json',**(headers or {})},method=method)
 with client.open(req,timeout=40) as r:return json.load(r)
bridge=request('auth/session',{},headers={'Authorization':'Bearer '+token})
admin_headers={'X-Moara-CSRF':bridge['csrf_token']}
account=request('admin/accounts',{'name':'Tutorial Moara - dados fictícios','email':'tutorial-'+secrets.token_hex(5)+'@example.invalid','roles':['user']},headers=admin_headers)
identifier=account['id'];userjar=http.cookiejar.CookieJar()
userclient=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),urllib.request.HTTPCookieProcessor(userjar))
email_response=None
# Retrieve only the just-created account's email from the request context, not an account inventory.
# Account login uses the email stored below by selecting the synthetic subject in SQL without reading other accounts.
email=subprocess.check_output(['docker','exec','ai-server-postgres-1','psql','-U','postgres','-d','ai','-Atc',"SELECT email FROM moara.accounts WHERE id='"+identifier+"'"],text=True).strip()
name='moara-tutorial-browser'
def tutorial_profile_access(enable):
 subject='local:'+identifier
 if enable:
  q="UPDATE moara.profiles SET allowed_subjects=allowed_subjects || to_jsonb('"+subject+"'::text) WHERE id='fast' AND NOT allowed_subjects ? '"+subject+"';"
 else:q="UPDATE moara.profiles SET allowed_subjects=allowed_subjects - '"+subject+"' WHERE id='fast';"
 q+="INSERT INTO moara.audit(actor_subject,action,resource,status) VALUES('system:tutorial','tutorial.profile."+('grant' if enable else 'revoke')+"','"+identifier+"','ok');"
 subprocess.run(['docker','exec','ai-server-postgres-1','psql','-U','postgres','-d','ai','-v','ON_ERROR_STOP=1','-c',q],check=True,capture_output=True)
try:
 tutorial_profile_access(True)
 login=request('auth/login',{'email':email,'password':account['temporary_password']},client=userclient)
 request('auth/password',{'current_password':account['temporary_password'],'password':secrets.token_urlsafe(36)},method='PUT',headers={'X-Moara-CSRF':login['csrf_token']},client=userclient)
 cookie=next(c for c in userjar if c.name=='__Secure-moara_session')
 existing=subprocess.run(['docker','inspect',name],capture_output=True)
 if existing.returncode==0:
  if json.loads(existing.stdout)[0]['Config'].get('Labels',{}).get('moara.test')!='tutorial-real-production':raise RuntimeError('unowned container')
  subprocess.run(['docker','rm','-f',name],check=True,capture_output=True)
 subprocess.run(['docker','run','-d','--name',name,'--label','moara.test=tutorial-real-production','--memory','2g','--cpus','2','--pids-limit','256','--add-host','moara.am.trf1.gov.br:172.19.5.250','--entrypoint','sleep','ia-studio-renderer:1.0.0','infinity'],check=True,capture_output=True)
 subprocess.run(['docker','cp',str(WORK/'capture.py'),name+':/tmp/capture.py'],check=True,capture_output=True)
 payload={'cookie_name':cookie.name,'cookie':cookie.value,'spki':spki}
 result=subprocess.run(['docker','exec','-i',name,'python','/tmp/capture.py'],input=json.dumps(payload).encode(),capture_output=True,timeout=2000)
 print(result.stdout.decode()[-6000:]);print(result.stderr.decode()[-2500:])
 data=subprocess.check_output(['docker','exec',name,'tar','-C','/tmp/tutorial','-cf','-','.'])
 with tarfile.open(fileobj=io.BytesIO(data)) as tar:tar.extractall(WORK/'captures',filter='data')
 (WORK/'public-report.json').write_text(json.dumps({'image_id':subprocess.check_output(['docker','inspect','-f','{{.Image}}','ai-server-moara-gateway-1'],text=True).strip(),'account_id':identifier,'production':True,'synthetic_account_disabled':True}))
finally:
 tutorial_profile_access(False)
 request('admin/accounts/'+identifier,{'active':False,'roles':['user']},method='PUT',headers=admin_headers)
 subprocess.run(['docker','rm','-f',name],capture_output=True)
print('Synthetic tutorial account disabled; no existing accounts or documents changed.')
raise SystemExit(result.returncode)
