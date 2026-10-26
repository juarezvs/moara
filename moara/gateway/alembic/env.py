import asyncio
from alembic import context
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from moara.gateway.settings import database_url

def migration(connection):
    context.configure(connection=connection,version_table='alembic_version',version_table_schema='moara',
        include_schemas=True,transaction_per_migration=True)
    with context.begin_transaction():context.run_migrations()

async def run():
    engine=create_async_engine(database_url('migration'),echo=False,hide_parameters=True)
    async with engine.connect() as conn:
        await conn.execute(text('SELECT pg_advisory_lock(42612552)'))
        await conn.commit()
        try:await conn.run_sync(migration)
        finally:
            await conn.execute(text('SELECT pg_advisory_unlock(42612552)'));await conn.commit()
    await engine.dispose()

asyncio.run(run())
