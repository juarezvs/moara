import json,subprocess
p=subprocess.run(['docker','inspect','moara-platform-qa-api'],capture_output=True,text=True);o=json.loads(p.stdout)[0];print(json.dumps({'restart_count':o['RestartCount'],'state':o['State']}))
query="""import asyncio,json
from moara.gateway.database import Database
from moara.gateway.settings import Settings
async def main():
 db=Database(Settings.load());rows=await db.execute("SELECT kind,status,error_code,created_at,started_at,updated_at,finished_at,lease_until,attempts FROM moara.platform_runs ORDER BY created_at DESC LIMIT 6")
 print(json.dumps(rows,default=str));await db.dispose()
asyncio.run(main())
"""
p=subprocess.run(['docker','exec','-i','moara-platform-qa-api','python','-'],input=query,capture_output=True,text=True);print(p.stdout)
p=subprocess.run(['docker','logs','--tail','30','moara-platform-qa-api'],capture_output=True,text=True);print(p.stderr[-6000:])
