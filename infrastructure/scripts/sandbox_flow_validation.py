import json,subprocess,time
from pathlib import Path
STAGE=Path('/home/nutec/moara-platform-20261026')
source="""import json,httpx
from pathlib import Path
c=httpx.Client(base_url='http://127.0.0.1:8075/api/v1/',headers={'Origin':'https://localhost:8443'},timeout=20)
r=c.post('auth/login',json={'email':'admin@staging.invalid','password':Path('/run/secrets/admin_password').read_text()});r.raise_for_status()
c.headers['Cookie']='__Secure-moara_session='+r.cookies.get('__Secure-moara_session');c.headers['X-Moara-CSRF']=r.json()['csrf_token']
r=c.post('platform/resources',json={'kind':'project','title':'Synthetic approved execution','body':{'language':'python','files':{'main.py':'print(17+25)'}}});r.raise_for_status();project=r.json()['id']
review=c.get('platform/projects/'+project+'/review');review.raise_for_status();body=review.json()
bad=c.post('platform/projects/'+project+'/execute',json={'version':body['version'],'digest':'0'*64})
assert bad.status_code==409
r=c.post('platform/projects/'+project+'/execute',json={'version':body['version'],'digest':body['digest']});r.raise_for_status()
print(json.dumps({'job':r.json()['id'],'project':project,'wrong_digest_denied':True}))
"""
p=subprocess.run(['docker','exec','-i','moara-platform-qa-api','python','-'],input=source,text=True,capture_output=True,timeout=60)
if p.returncode:print(p.stderr[-2000:]);raise SystemExit(1)
fixture=json.loads(p.stdout)
p=subprocess.run(['python3',str(STAGE/'sandbox_worker.py'),'--api','moara-platform-qa-api','--once'],capture_output=True,text=True,timeout=90)
if p.returncode:print(p.stderr[-1000:]);raise SystemExit(1)
verify="""import asyncio,json
from moara.gateway.database import Database
from moara.gateway.settings import Settings
async def main():
 s=Settings.load();db=Database(s)
 row=await db.execute("SELECT status,result FROM moara.platform_runs WHERE id=CAST(:id AS uuid)",{'id':JOB},one=True)
 result=json.loads(s.fernet().decrypt(row['result'].encode())) if row['result'] else {}
 assert row['status']=='completed' and result['exit_code']==0 and result['output'].strip()=='42'
 print(json.dumps({'digest_bound_approval':True,'durable_execution':True,'output':'42','synthetic_only':True}))
 await db.dispose()
asyncio.run(main())
""".replace('JOB',repr(fixture['job']))
p=subprocess.run(['docker','exec','-i','moara-platform-qa-api','python','-'],input=verify,text=True,capture_output=True,timeout=60)
print(p.stdout);print(p.stderr[-2000:]);raise SystemExit(p.returncode)
