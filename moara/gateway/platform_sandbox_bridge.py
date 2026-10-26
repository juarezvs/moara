"""Private stdin/stdout protocol used exclusively by the host sandbox worker."""
import asyncio,json,sys,uuid
from types import SimpleNamespace
import httpx
from .auth import Auth
from .database import Database
from .settings import Settings
from . import platform_store as store
from .platform_runs import fresh_actor
async def main():
 request=json.loads(sys.stdin.read(150000));settings=Settings.load();db=Database(settings)
 async with httpx.AsyncClient(trust_env=False,timeout=10) as http:
  auth=Auth(settings,db,http);app=SimpleNamespace(state=SimpleNamespace(settings=settings,db=db,auth=auth))
  try:
   mode=request['mode']
   if mode=='claim':
    row=await db.execute("""UPDATE moara.platform_runs SET status='running',started_at=now(),lease_until=now()+interval '90 seconds',attempts=attempts+1
    WHERE id=(SELECT id FROM moara.platform_runs WHERE kind='project.execute' AND status='queued' AND approved_at IS NOT NULL AND NOT cancel_requested
     ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING *""",one=True)
   else:
    identifier=str(uuid.UUID(request['id']))
    row=await db.execute("SELECT * FROM moara.platform_runs WHERE id=CAST(:id AS uuid) AND kind='project.execute' AND status='running'",{'id':identifier},one=True)
   if not row:return {'available':False}
   payload=store.unseal(app,row['payload'])
   try:
    actor=await fresh_actor(app,row,payload)
    resource=await store.get(app,actor,row['resource_id'],kind='project',write=True)
    if row['cancel_requested'] or resource['version']!=payload['resource']['version'] or store.digest(resource['body'].get('files',{}))!=row['approval_digest']:raise ValueError()
   except Exception:
    await db.execute("UPDATE moara.platform_runs SET status='cancelled',error_code='execution_approval_revoked',finished_at=now() WHERE id=CAST(:id AS uuid)",{'id':str(row['id'])})
    return {'available':False}
   if mode=='finish':
    result=request['result']
    if not isinstance(result,dict) or len(json.dumps(result))>100000:raise ValueError()
    await db.execute("""UPDATE moara.platform_runs SET status='completed',result=:result,lease_until=NULL,finished_at=now(),updated_at=now()
     WHERE id=CAST(:id AS uuid) AND status='running'""",{'id':str(row['id']),'result':store.seal(app,result)})
    await db.audit(actor,'project.execution.finished',row['id']);return {'stored':True}
   await db.execute("UPDATE moara.platform_runs SET lease_until=now()+interval '90 seconds',updated_at=now() WHERE id=CAST(:id AS uuid)",{'id':str(row['id'])})
   if mode=='check':return {'available':True}
   if mode!='claim':raise ValueError()
   return {'available':True,'id':str(row['id']),'files':resource['body'].get('files',{}),'language':resource['body'].get('language','python')}
  finally:await auth.close();await db.dispose()
if __name__=='__main__':
 try:print(json.dumps(asyncio.run(main())))
 except Exception:print('{"error":"sandbox_bridge_failed"}');sys.exit(1)
