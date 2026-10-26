"""SQLAlchemy pool and parameterized access to the versioned Moara schema."""
import json
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

class Database:
    def __init__(self,settings):
        self.engine=create_async_engine(settings.db_url,pool_size=5,max_overflow=2,pool_timeout=15,
            pool_pre_ping=True,echo=False,hide_parameters=True,connect_args={'connect_timeout':10,
                'options':'-c statement_timeout=15000 -c lock_timeout=3000'})

    async def execute(self,statement,params=None,*,one=False,conn=None):
        if conn is None:
            async with self.engine.begin() as connection:
                return await self.execute(statement,params,one=one,conn=connection)
        result=await conn.execute(text(statement),params or {})
        if result.returns_rows:
            rows=result.mappings()
            row=rows.first() if one else rows.all()
            return dict(row) if one and row is not None else [dict(r) for r in row] if not one else None

    async def audit(self,actor,action,resource=None,*,status='ok',error=None,request_id=None,conn=None):
        await self.execute('''INSERT INTO moara.audit(actor_subject,api_key_id,action,resource,status,error_code,request_id)
            VALUES(:actor,CAST(:key AS uuid),:action,:resource,:status,:error,CAST(:request AS uuid))''',
            {'actor':actor.subject if actor else 'system','key':str(actor.key_id) if actor and actor.key_id else None,
                'action':action,'resource':str(resource)[:160] if resource else None,'status':status,'error':error,
                'request':str(request_id) if request_id else None},conn=conn)

    async def dispose(self):await self.engine.dispose()

def as_json(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'))
