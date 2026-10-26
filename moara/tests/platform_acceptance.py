"""Real isolated API/PG/Redis tests using only generated fictitious users and records."""
import asyncio,base64,json,secrets,time,uuid
from pathlib import Path
import httpx
from moara.gateway.database import Database
from moara.gateway.settings import Settings
from moara.gateway.auth import PASSWORDS
checks=[]
def check(name,value):
 checks.append({'name':name,'passed':bool(value)})
 if not value:raise AssertionError(name)
class Client:
 def __init__(self):self.http=httpx.Client(base_url='http://127.0.0.1:8075/api/v1/',headers={'Origin':'https://localhost:8443'},timeout=30);self.csrf=''
 def req(self,method,path,body=None):
  return self.http.request(method,path,json=body,headers={'X-Moara-CSRF':self.csrf} if self.csrf else {})
 def login(self,email,password):
  r=self.req('POST','auth/login',{'email':email,'password':password});check('login_'+email,r.status_code==200)
  self.http.headers['Cookie']='__Secure-moara_session='+r.cookies.get('__Secure-moara_session');self.csrf=r.json()['csrf_token']
 def ok(self,method,path,body=None,status=200):
  r=self.req(method,'platform/'+path,body);check(method+' '+path+' '+str(r.status_code),r.status_code==status);return r.json()
async def seed():
 db=Database(Settings.load());password=secrets.token_hex(24);users=[]
 for name in ('alice','bob'):
  identifier=uuid.uuid4();users.append(identifier)
  await db.execute("INSERT INTO moara.accounts(id,subject,name,email,auth_source,password_hash) VALUES(CAST(:id AS uuid),:subject,:name,:email,'local',:hash)",{'id':str(identifier),'subject':'local:'+str(identifier),'name':name,'email':name+'@platform.invalid','hash':PASSWORDS.hash(password)})
  await db.execute("INSERT INTO moara.account_roles(account_id,role_id) VALUES(CAST(:id AS uuid),'user')",{'id':str(identifier)})
 group=uuid.uuid4()
 await db.execute("INSERT INTO moara.groups(id,name) VALUES(CAST(:id AS uuid),'Synthetic platform team')",{'id':str(group)})
 for user in users:await db.execute("INSERT INTO moara.group_members(group_id,account_id) VALUES(CAST(:g AS uuid),CAST(:u AS uuid))",{'g':str(group),'u':str(user)})
 await db.dispose();return password,users,group
password,users,group=asyncio.run(seed());a=Client();b=Client();a.login('alice@platform.invalid',password);b.login('bob@platform.invalid',password)
check('unauthenticated_denied',httpx.get('http://127.0.0.1:8075/api/v1/platform/resources').status_code==401)
a.ok('GET','agents')
prompt=a.ok('POST','resources',{'kind':'prompt','title':'Private prompt','body':{'text':'Synthetic secret'}},201)
check('private_read_denied',b.req('GET','platform/resources/'+prompt['id']).status_code==404)
a.ok('PUT','resources/'+prompt['id'],{'version':1,'title':'Shared prompt','body':{'text':'Synthetic shared'},'group_id':str(group)})
b.ok('GET','resources/'+prompt['id'])
check('shared_write_denied',b.req('PUT','platform/resources/'+prompt['id'],{'version':2,'title':'Changed','body':{'text':'x'}}).status_code==403)
check('stale_version_denied',a.req('PUT','platform/resources/'+prompt['id'],{'version':1,'title':'Changed','body':{'text':'x'}}).status_code==409)
check('version_history',len(a.ok('GET','resources/'+prompt['id']+'/versions'))==2)
async def revoke():
 db=Database(Settings.load());await db.execute('DELETE FROM moara.group_members WHERE group_id=CAST(:g AS uuid) AND account_id=CAST(:u AS uuid)',{'g':str(group),'u':str(users[1])});await db.dispose()
asyncio.run(revoke());check('group_revocation_immediate',b.req('GET','platform/resources/'+prompt['id']).status_code==404)
doc=a.ok('POST','documents',{'filename':'synthetic.csv','title':'Synthetic dataset','content_base64':base64.b64encode(b'area,dias\nA,2\nA,4\nB,8\n').decode()},201)
check('private_download_denied',b.req('GET','platform/documents/'+doc['id']+'/download').status_code==404)
result=a.ok('POST','analytics/query',{'document_id':doc['id'],'group_by':'area','operation':'average','value_column':'dias'})
check('real_analytics',result['rows'][0]['value']=='3')
check('analytics_source_acl',b.req('POST','platform/analytics/query',{'document_id':doc['id'],'group_by':'area'}).status_code==404)
template=a.ok('POST','resources',{'kind':'template','title':'Synthetic template','body':{'text':'Olá {{nome}}','variables':['nome']}},201)
result=a.ok('POST','templates/'+template['id']+'/render',{'version':1,'fields':{'nome':'Pessoa fictícia'}})
check('docx_generated',base64.b64decode(result['docx_base64']).startswith(b'PK'))
flow=a.ok('POST','resources',{'kind':'workflow','title':'Synthetic test','body':{'steps':[{'type':'notification.test','parameters':{'message':'Synthetic only'}}]}},201)
payload={'operation':'workflow.run','resource_id':flow['id'],'input':{},'idempotency_key':'same-test'}
job=a.ok('POST','runs',payload,202);same=a.ok('POST','runs',payload,202);check('idempotency',job['id']==same['id'])
check('idempotency_conflict',a.req('POST','platform/runs',{**payload,'input':{'query':'changed'}}).status_code==409)
for _ in range(30):
 result=a.ok('GET','runs/'+job['id'])
 if result['status'] not in ('queued','running'):break
 time.sleep(1)
check('durable_workflow_completed',result['status']=='completed')
check('no_external_notification',result['result']['steps'][0]['result']['delivered'] is False)
check('private_job_denied',b.req('GET','platform/runs/'+job['id']).status_code==404)
check('forbidden_tool',a.req('POST','platform/resources',{'kind':'workflow','title':'bad','body':{'steps':[{'type':'shell'}]}}).status_code==422)
async def storage():
 db=Database(Settings.load())
 row=await db.execute('SELECT body FROM moara.resources WHERE id=CAST(:id AS uuid)',{'id':prompt['id']},one=True)
 check('resource_encrypted','Synthetic' not in row['body'])
 try:await db.execute("UPDATE moara.audit SET status='tampered' WHERE id=(SELECT min(id) FROM moara.audit)")
 except Exception:check('audit_append_only',True)
 else:check('audit_append_only',False)
 await db.dispose()
asyncio.run(storage())
print('PLATFORM_REPORT='+json.dumps({'checks':checks,'passed':all(c['passed'] for c in checks),'synthetic_only':True,'production_modified':False}))
