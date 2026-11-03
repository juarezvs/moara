import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from gpu_remote import source
script=r'''
cd /home/nutec/ai-server
hostname
cat /etc/os-release | head -5
free -b
lscpu | head -18
df -B1 /
docker ps --format '{{.Names}} {{.Image}} {{.Status}}'
docker volume ls --format '{{.Name}}'
systemctl --user is-active ai-server.service
systemctl --user is-enabled ai-server.service
find backups -maxdepth 1 -type f -printf '%f %s %TY-%Tm-%TdT%TH:%TM\n' | sort | tail -10
docker exec -i ai-server-moara-gateway-1 python - <<'PY'
import asyncio,json
from moara.gateway.database import Database
from moara.gateway.settings import Settings
async def main():
 db=Database(Settings.load())
 queries={
 'resources':"SELECT kind,count(*) AS count FROM moara.resources WHERE NOT archived GROUP BY kind ORDER BY kind",
 'jobs':"SELECT status,count(*) AS count FROM moara.platform_runs GROUP BY status ORDER BY status",
 'models':"SELECT id,display_name,family,context_length,installed,capabilities FROM moara.models ORDER BY display_name",
 'profiles':"SELECT id,name,enabled,manual_allowed,settings FROM moara.profiles ORDER BY id",
 'active_identity':"SELECT version,sha256,body->>'name' AS name,body->>'product' AS product,body->>'signature' AS signature FROM moara.identity_versions WHERE status='active'",
 'schema':"SELECT version_num FROM moara.alembic_version",
 'evidence_permissions':"SELECT has_table_privilege(current_user,'moara.legal_evidence','UPDATE') AS update,has_table_privilege(current_user,'moara.legal_evidence','DELETE') AS delete,has_table_privilege(current_user,'moara.legal_evidence','TRUNCATE') AS truncate"
 }
 result={}
 for key,sql in queries.items():
  try:result[key]=await db.execute(sql)
  except Exception as error:result[key]={'error_type':type(error).__name__}
 print(json.dumps(result,default=str,ensure_ascii=True))
 await db.dispose()
asyncio.run(main())
PY
'''
output=source(script,timeout=90)
target=Path('output/moara2');target.mkdir(parents=True,exist_ok=True)
(target/'source-inventory-20261030.txt').write_text(output,encoding='utf-8')
print(output.encode('ascii',errors='backslashreplace').decode())
