import subprocess,json
logs=subprocess.check_output(['docker','logs','--since','5m','ai-server-moara-gateway-1'],stderr=subprocess.STDOUT).decode(errors='replace')
print(json.dumps({'dispatch_errors_last_5m':logs.count('platform_dispatch_unavailable')}))
code="""import asyncio,json
from moara.gateway.database import Database
from moara.gateway.settings import Settings
async def main():
 db=Database(Settings.load())
 for name,q in [
 ('schedule',\"EXPLAIN UPDATE moara.flow_schedules SET next_run=now()+make_interval(secs=>interval_seconds) WHERE resource_id IN (SELECT resource_id FROM moara.flow_schedules WHERE enabled AND next_run<=now() ORDER BY next_run LIMIT 4 FOR UPDATE SKIP LOCKED) RETURNING resource_id,extract(epoch FROM next_run)::bigint AS stamp\"),
 ('expiry',\"EXPLAIN UPDATE moara.platform_runs SET status='failed',error_code='worker_lease_expired',finished_at=now() WHERE status='running' AND lease_until<now()\"),
 ('claim',\"EXPLAIN UPDATE moara.platform_runs SET status='running',started_at=now(),attempts=attempts+1,lease_until=now()+interval '90 seconds' WHERE id=(SELECT id FROM moara.platform_runs WHERE status='queued' AND kind<>'project.execute' AND NOT cancel_requested ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING *\")]:
  try:await db.execute(q);print(name+':ok')
  except Exception as e:print(json.dumps({'query':name,'error':type(e).__name__,'sqlstate':getattr(getattr(e,'orig',None),'sqlstate',None)}))
 await db.dispose()
asyncio.run(main())
"""
p=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-'],input=code.encode(),capture_output=True)
print(p.stdout.decode());print(p.stderr.decode()[-500:])
