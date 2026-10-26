"""Database-backed schedules for fixed workflow operations."""
from fastapi import HTTPException
async def configure(app,actor,identifier,body,conn):
 actor.require('workflows.use')
 schedule=body.get('schedule',{});enabled=schedule.get('enabled',False)
 if actor.key_id and enabled:raise HTTPException(403,'interactive_schedule_required')
 await app.state.db.execute("""INSERT INTO moara.flow_schedules(resource_id,enabled,interval_seconds,next_run)
 VALUES(CAST(:id AS uuid),:enabled,:seconds,now()+make_interval(secs=>:seconds))
 ON CONFLICT(resource_id) DO UPDATE SET enabled=EXCLUDED.enabled,interval_seconds=EXCLUDED.interval_seconds,next_run=EXCLUDED.next_run""",
 {'id':str(identifier),'enabled':enabled,'seconds':schedule.get('interval_seconds',3600)},conn=conn)
async def tick(app):
 from .platform_runs import enqueue
 from .platform_contracts import RunCreate
 rows=await app.state.db.execute("""UPDATE moara.flow_schedules SET next_run=now()+make_interval(secs=>interval_seconds)
 WHERE resource_id IN (SELECT resource_id FROM moara.flow_schedules WHERE enabled AND next_run<=now()
 ORDER BY next_run LIMIT 4 FOR UPDATE SKIP LOCKED) RETURNING resource_id,extract(epoch FROM next_run)::bigint AS stamp""")
 for schedule in rows:
  identifier=str(schedule['resource_id'])
  try:
   resource=await app.state.db.execute('SELECT owner_id FROM moara.resources WHERE id=CAST(:id AS uuid) AND NOT archived',{'id':identifier},one=True)
   if not resource:raise HTTPException(404,'resource_not_found')
   account=await app.state.db.execute('SELECT * FROM moara.accounts WHERE id=CAST(:id AS uuid)',{'id':str(resource['owner_id'])},one=True)
   actor=await app.state.auth.from_row(account);actor.require('workflows.use')
   result=await enqueue(app,actor,RunCreate(operation='workflow.run',resource_id=identifier,input={},idempotency_key='schedule:'+identifier+':'+str(schedule['stamp'])))
   await app.state.db.execute('UPDATE moara.flow_schedules SET last_run=CAST(:run AS uuid) WHERE resource_id=CAST(:id AS uuid)',{'run':result['id'],'id':identifier})
  except HTTPException as exc:
   if exc.status_code in (403,404):await app.state.db.execute('UPDATE moara.flow_schedules SET enabled=false WHERE resource_id=CAST(:id AS uuid)',{'id':identifier})
   await app.state.db.audit(None,'workflow.schedule.deferred',identifier,status='error',error='schedule_not_authorized_or_busy')
  except Exception:await app.state.db.audit(None,'workflow.schedule.deferred',identifier,status='error',error='schedule_unavailable')
