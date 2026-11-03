import pathlib,importlib.util,subprocess
root=pathlib.Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import sys,json,time,urllib.request,http.cookies,asyncio,hashlib
token=sys.stdin.readline().strip();cookie=None
def req(path,body,headers):
 r=urllib.request.Request('http://localhost:8075'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json',**headers})
 return urllib.request.urlopen(r,timeout=40)
try:
 for native in (False,True):
  headers={'Authorization':'Bearer '+token}
  if native:
   with req('/api/v1/auth/session',{},headers) as r:
    jar=http.cookies.SimpleCookie();jar.load(r.headers['Set-Cookie']);cookie=jar['__Secure-moara_session'].value;csrf=json.load(r)['csrf_token']
   headers={'Cookie':'__Secure-moara_session='+cookie,'X-Moara-CSRF':csrf,'Origin':'https://moara.am.trf1.gov.br'}
  body={'model':'auto','messages':[{'role':'user','content':'CPC art.12; data de referência: 2020-01-01'}],'stream':True}
  start=time.monotonic()
  try:
   with req('/api/v1/chat/stream',body,headers) as r:
    data=r.read().decode();assert '[DONE]' in data;print(json.dumps({'native':native,'seconds':round(time.monotonic()-start,2),'bytes':len(data),'ok':True}),flush=True)
  except Exception as e:print(json.dumps({'native':native,'seconds':round(time.monotonic()-start,2),'error':type(e).__name__}),flush=True)
finally:
 if cookie:
  from moara.gateway.database import Database
  from moara.gateway.settings import Settings
  async def clean():
   db=Database(Settings.load());await db.execute('UPDATE moara.sessions SET revoked_at=now() WHERE token_hash=:hash',{'hash':hashlib.sha256(cookie.encode()).hexdigest()});await db.dispose()
  asyncio.run(clean())
'''
r=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session()+'\n',text=True,capture_output=True,timeout=110)
print(r.stdout,flush=True)
if r.returncode:print(r.stderr[-1400:]);raise SystemExit(r.returncode)
