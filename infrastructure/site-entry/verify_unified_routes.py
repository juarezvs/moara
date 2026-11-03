import pathlib,subprocess,json,sys
ROOT=pathlib.Path('/home/nutec/ai-server');public='--public' in sys.argv
base='https://moara.am.trf1.gov.br' if public else 'http://'+(ROOT/'tmp/unified-proxy-name.txt').read_text().strip()+':8080'
code=r'''
import httpx,json,sys,ssl
from pathlib import Path
base=sys.argv[1];ctx=ssl.create_default_context();ctx.load_verify_locations(cafile='/app/web/integrations/moara-domain-root-ca.crt')
checks={};results=[]
with httpx.Client(timeout=20,trust_env=False,verify=ctx,follow_redirects=False) as client:
 for method,path in [('GET','/'),('HEAD','/'),('GET','/?interface=anterior'),('GET','/?q=qualquer'),('GET','/chat-anterior'),('GET','/auth'),('GET','/workspace'),('GET','/assets/previous-ui.js'),('GET','/c/11111111-1111-4111-8111-111111111111'),('GET','/moara/chat'),('GET','/moara/api/v1/ready'),('GET','/api/v1/chats/list'),('GET','/moara/v1/models')]:
  r=client.request(method,base+path);key=method+' '+path
  if path.startswith('/c/'):valid=r.status_code==302 and r.headers.get('location')=='/moara/chat?previous=11111111-1111-4111-8111-111111111111'
  elif path=='/chat-anterior':valid=r.status_code==302 and r.headers.get('location')=='/moara/chat?area=historico'
  elif path in ['/moara/chat']:valid=r.status_code==200 and '<base href="/moara/">' in r.text
  elif path.endswith('/ready'):valid=r.status_code==200 and r.json()['status']=='ready'
  elif path.endswith('/chats/list') or path=='/moara/v1/models':valid=r.status_code in (401,403) and 'application/json' in r.headers.get('content-type','')
  else:valid=r.status_code==302 and r.headers.get('location')=='/moara/chat'
  checks[key]=valid;results.append({'path':path,'status':r.status_code,'location':r.headers.get('location')})
 print(json.dumps({'checks':checks,'routes':results}));assert all(checks.values()),checks
'''
args=['docker','run','--rm','-i','--network','ai-server_download' if public else 'ai-server_frontend','--read-only','--tmpfs','/tmp:size=32m','--memory','256m','--cpus','1','--cap-drop','ALL','--entrypoint','python','moara-core:unified-20261031','-',base]
r=subprocess.run(args,input=code,text=True,capture_output=True,timeout=90)
if r.stdout:
 data=json.loads(r.stdout.strip().splitlines()[-1]);(ROOT/'docs/runtime'/('unified-routes-public.json' if public else 'unified-routes-stage.json')).write_text(json.dumps(data,indent=2));print(json.dumps(data))
if r.returncode:print(r.stderr[-1000:].split('Call log:')[0])
raise SystemExit(r.returncode)
