import base64
import hashlib
import json
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from cryptography.fernet import Fernet

PASSWORD=Path('/run/secrets/db_password').read_text().strip()
CRYPTO=Fernet(base64.urlsafe_b64encode(hashlib.sha256(Path('/run/secrets/connector_crypto_key').read_bytes()).digest()))

async def sql(statement,params=(),one=False):
    async with await psycopg.AsyncConnection.connect(host='postgres',dbname='ai',user='ai_app',password=PASSWORD,
            autocommit=True,row_factory=dict_row) as conn:
        cur=await conn.execute(statement,params)
        if cur.description:return await cur.fetchone() if one else await cur.fetchall()

async def migrate():
    async with await psycopg.AsyncConnection.connect(host='postgres',dbname='ai',user='ai_app',password=PASSWORD) as conn:
        await conn.execute('SELECT pg_advisory_xact_lock(42612551)')
        await conn.execute('CREATE SCHEMA IF NOT EXISTS connector_center')
        await conn.execute('CREATE TABLE IF NOT EXISTS connector_center.migrations(version integer PRIMARY KEY,applied_at timestamptz NOT NULL DEFAULT now())')
        applied={r[0] for r in await (await conn.execute('SELECT version FROM connector_center.migrations')).fetchall()}
        for path in sorted(Path('/app/connectors/migrations').glob('*.sql')):
            if int(path.name.split('_')[0]) not in applied:await conn.execute(path.read_text())
        # Legacy development runs are encrypted in-place before the service starts.
        rows=await (await conn.execute('SELECT id,question,result FROM connector_center.runs')).fetchall()
        from psycopg.types.json import Jsonb
        for identifier,question,result in rows:
            if not question.startswith('enc:v1:'):
                await conn.execute('UPDATE connector_center.runs SET question=%s WHERE id=%s',(pack(question),identifier))
            if result and 'encrypted_v1' not in result:
                await conn.execute('UPDATE connector_center.runs SET result=%s WHERE id=%s',(Jsonb({'encrypted_v1':pack(result)}),identifier))
        await conn.execute('DELETE FROM connector_center.runs WHERE expires_at<now()')
        await conn.execute("UPDATE connector_center.runs SET status='failed',error='Consulta interrompida pelo reinício; envie uma nova solicitação.' WHERE status IN ('queued','running')")

def encrypt(value):return CRYPTO.encrypt(json.dumps(value).encode()) if value is not None else None
def decrypt(value):return json.loads(CRYPTO.decrypt(bytes(value))) if value else {}

def pack(value):return 'enc:v1:'+CRYPTO.encrypt(json.dumps(value,ensure_ascii=False).encode()).decode()
def unpack(value):
    if not isinstance(value,str) or not value.startswith('enc:v1:'):raise ValueError('Private run integrity failure')
    return json.loads(CRYPTO.decrypt(value[7:].encode()))

async def enqueue_run(identifier,owner,question,model):
    async with await psycopg.AsyncConnection.connect(host='postgres',dbname='ai',user='ai_app',password=PASSWORD) as conn:
        await conn.execute('SELECT pg_advisory_xact_lock(42612556)')
        total,own=await (await conn.execute("SELECT count(*),count(*) FILTER(WHERE owner=%s) FROM connector_center.runs WHERE status IN ('queued','running')",(owner,))).fetchone()
        if total>=8 or own>=2:return False
        await conn.execute("INSERT INTO connector_center.runs(id,owner,status,question,model) VALUES(%s,%s,'queued',%s,%s)",(identifier,owner,pack(question),model))
    return True

async def remove_source(identifier,name,owner):
    async with await psycopg.AsyncConnection.connect(host='postgres',dbname='ai',user='ai_app',password=PASSWORD,row_factory=dict_row) as conn:
        row=await (await conn.execute('SELECT name,active FROM connector_center.sources WHERE id=%s FOR UPDATE',(identifier,))).fetchone()
        if not row:return 'missing'
        if row['name']!=name:return 'confirmation'
        if row['active']:return 'active'
        used=await (await conn.execute('SELECT id FROM connector_center.relationships WHERE left_source=%s OR right_source=%s LIMIT 1',(identifier,identifier))).fetchone()
        if used:return 'mapped'
        present=await (await conn.execute("SELECT to_regclass('connector_center.semantic_embeddings') AS name")).fetchone()
        if present['name']:await conn.execute('DELETE FROM connector_center.semantic_embeddings WHERE source_id=%s',(identifier,))
        await conn.execute('DELETE FROM connector_center.sources WHERE id=%s',(identifier,))
        await conn.execute("INSERT INTO connector_center.audit(owner,action,source_id,status) VALUES(%s,'source.delete',%s,'ok')",(owner,identifier))
    return 'removed'
