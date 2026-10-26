import asyncio,json,time,uuid
from pathlib import Path
import httpx
from moara.gateway.database import Database
from moara.gateway.settings import Settings
async def main():
 async with httpx.AsyncClient(base_url='http://127.0.0.1:8075/api/v1/',headers={'Origin':'https://localhost:8443'},timeout=30) as client:
  r=await client.post('auth/login',json={'email':'admin@staging.invalid','password':Path('/run/secrets/admin_password').read_text()});r.raise_for_status()
  client.headers['Cookie']='__Secure-moara_session='+r.cookies.get('__Secure-moara_session');client.headers['X-Moara-CSRF']=r.json()['csrf_token']
  r=await client.post('platform/resources',json={'kind':'prompt','title':'Concurrent synthetic resource','body':{'text':'initial'}});r.raise_for_status();resource=r.json()['id']
  started=time.monotonic()
  rows=await asyncio.gather(*[client.put('platform/resources/'+resource,json={'version':1,'title':'Concurrent synthetic '+str(i),'body':{'text':str(i)}}) for i in range(12)])
  checks={'concurrent_one_winner':sum(r.status_code==200 for r in rows)==1,'concurrent_conflicts_explicit':sum(r.status_code==409 for r in rows)==11}
  latency=time.monotonic()-started
  r=await client.post('platform/resources',json={'kind':'workflow','title':'Scheduled synthetic workflow','body':{'steps':[{'type':'notification.test','parameters':{'message':'synthetic'}}],'schedule':{'enabled':True,'interval_seconds':300}}});r.raise_for_status();flow=r.json()['id']
  key=str(uuid.uuid4());payload={'operation':'workflow.run','resource_id':flow,'input':{},'idempotency_key':key}
  rows=await asyncio.gather(*[client.post('platform/runs',json=payload) for _ in range(12)])
  checks['concurrent_idempotency']=all(r.status_code==202 for r in rows) and len({r.json()['id'] for r in rows})==1
  db=Database(Settings.load())
  await db.execute("UPDATE moara.flow_schedules SET next_run=now()-interval '1 second' WHERE resource_id=CAST(:id AS uuid)",{'id':flow})
  for _ in range(20):
   row=await db.execute('SELECT last_run FROM moara.flow_schedules WHERE resource_id=CAST(:id AS uuid)',{'id':flow},one=True)
   if row['last_run']:break
   await asyncio.sleep(1)
  checks['durable_schedule_dispatched']=bool(row['last_run'])
  await db.execute('UPDATE moara.flow_schedules SET enabled=false WHERE resource_id=CAST(:id AS uuid)',{'id':flow});await db.dispose()
  assert all(checks.values()),json.dumps(checks)
  print(json.dumps({'checks':checks,'concurrent_requests':12,'version_conflict_batch_seconds':round(latency,3),'scope':'isolated API synthetic smoke load, not capacity certification'}))
asyncio.run(main())
