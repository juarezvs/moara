import pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from gpu_remote import source
print(source(r'''docker exec -i ai-server-moara-gateway-1 python - <<'PY'
import asyncio,json
from moara.gateway.settings import Settings
from moara.gateway.database import Database
async def main():
 db=Database(Settings.load())
 rows=await db.execute("SELECT a.auth_source,CASE WHEN a.subject LIKE 'key:%' THEN a.subject ELSE split_part(a.subject,':',1) END AS identity_type FROM moara.requests r JOIN moara.accounts a ON a.id=r.account_id WHERE r.id='8056c6fb-8f2d-4ebe-8356-03c16b4d317e'::uuid")
 print(json.dumps(rows));await db.dispose()
asyncio.run(main())
PY
'''))
