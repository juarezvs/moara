import asyncio,json
from moara.gateway.database import Database
from moara.gateway.settings import Settings

async def main():
    db=Database(Settings.load())
    row=await db.execute("""SELECT has_table_privilege(current_user,'moara.legal_evidence','SELECT') AS read,
      has_table_privilege(current_user,'moara.legal_evidence','INSERT') AS append,
      has_table_privilege(current_user,'moara.legal_evidence','UPDATE') AS update,
      has_table_privilege(current_user,'moara.legal_evidence','DELETE') AS delete,
      has_table_privilege(current_user,'moara.legal_evidence','TRUNCATE') AS truncate""",one=True)
    assert row['read'] and row['append'] and not any(row[k] for k in ('update','delete','truncate')),row
    jobs=await db.execute("SELECT count(*) AS running FROM moara.platform_runs WHERE status='running'",one=True)
    print(json.dumps({'evidence_privileges':row,'running_jobs':jobs['running']}))
    await db.dispose()

asyncio.run(main())
