"""PostgreSQL owns job state; Redis messages carry only job UUIDs."""
import asyncio
import hashlib
import uuid
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from .auth import require
from .database import as_json
from .model_catalog import APPROVED
router=APIRouter(prefix='/api/v1',tags=['Managed jobs'])

class Install(BaseModel):
    model_config=ConfigDict(extra='forbid')
    catalog_id:str
    idempotency_key:str=Field(min_length=8,max_length=100,pattern=r'^[a-zA-Z0-9_-]+$')

class Benchmark(BaseModel):
    model_config=ConfigDict(extra='forbid')
    model_id:uuid.UUID
    contexts:list[int]=Field(default=[8192],min_length=1,max_length=2)
    threads:list[int]=Field(default=[12],min_length=1,max_length=2)
    idempotency_key:str=Field(min_length=8,max_length=100,pattern=r'^[a-zA-Z0-9_-]+$')

class ModelOperation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    model_id:uuid.UUID
    expected_digest:str=Field(min_length=32,max_length=100)
    confirmation_name:str|None=Field(default=None,max_length=180)
    idempotency_key:str=Field(min_length=8,max_length=100,pattern=r'^[a-zA-Z0-9_-]+$')

async def managed_model(request,identifier):
    model=await request.app.state.db.execute('SELECT * FROM moara.models WHERE id=CAST(:id AS uuid)',{'id':str(identifier)},one=True)
    if not model:raise HTTPException(404,'model_not_found')
    if model['protected']:raise HTTPException(409,'preserved_legacy_model_protected')
    return model

@router.post('/admin/model-updates',status_code=202)
async def update(body:ModelOperation,request:Request,actor=Depends(require('models.install'))):
    if actor.key_id or actor.auth_source=='integration':raise HTTPException(403,'interactive_session_required')
    model=await managed_model(request,body.model_id)
    if model['digest']!=body.expected_digest:raise HTTPException(409,'model_version_changed')
    catalog_id=model['settings'].get('catalog_id')
    if catalog_id not in APPROVED:raise HTTPException(409,'model_not_in_approved_catalog')
    return await enqueue(request,actor,'model.update',{'catalog_id':catalog_id,'mode':'update'},body.idempotency_key)

@router.post('/admin/model-removals',status_code=202)
async def remove(body:ModelOperation,request:Request,actor=Depends(require('models.remove'))):
    if actor.key_id or actor.auth_source=='integration':raise HTTPException(403,'interactive_session_required')
    model=await managed_model(request,body.model_id)
    if model['digest']!=body.expected_digest or body.confirmation_name!=model['display_name']:raise HTTPException(409,'model_removal_confirmation_mismatch')
    used=await request.app.state.db.execute('''SELECT p.id FROM moara.profile_models pm JOIN moara.profiles p ON p.id=pm.profile_id
        WHERE pm.model_id=CAST(:id AS uuid) AND p.enabled LIMIT 1''',{'id':str(body.model_id)},one=True)
    if used:raise HTTPException(409,'model_has_enabled_profiles')
    return await enqueue(request,actor,'model.remove',{'model_id':str(body.model_id),'expected_digest':body.expected_digest,'confirmation_name':body.confirmation_name},body.idempotency_key)

async def enqueue(request,actor,kind,payload,idempotency):
    serialized=as_json(payload);checksum=hashlib.sha256(serialized.encode()).hexdigest();identifier=uuid.uuid4();db=request.app.state.db
    async with db.engine.begin() as conn:
        await db.execute('SELECT pg_advisory_xact_lock(42612555)',conn=conn)
        old=await db.execute('SELECT id,payload_hash,status FROM moara.jobs WHERE account_id=CAST(:account AS uuid) AND kind=:kind AND idempotency_key=:key',
            {'account':str(actor.user_id),'kind':kind,'key':idempotency},one=True,conn=conn)
        if old:
            if old['payload_hash']!=checksum:raise HTTPException(409,'idempotency_payload_mismatch')
            return {'id':str(old['id']),'status':old['status'],'reused':True}
        counts=await db.execute("SELECT count(*) AS total FROM moara.jobs WHERE status IN ('queued','running')",one=True,conn=conn)
        if counts['total']>=8:raise HTTPException(429,'job_queue_full')
        await db.execute('''INSERT INTO moara.jobs(id,account_id,api_key_id,kind,payload,payload_hash,idempotency_key)
            VALUES(CAST(:id AS uuid),CAST(:account AS uuid),CAST(:key_id AS uuid),:kind,:payload,:hash,:idempotency)''',
            {'id':str(identifier),'account':str(actor.user_id),'key_id':str(actor.key_id) if actor.key_id else None,'kind':kind,
                'payload':request.app.state.settings.fernet().encrypt(serialized.encode()).decode(),'hash':checksum,'idempotency':idempotency},conn=conn)
        await db.audit(actor,'job.create',identifier,request_id=request.state.request_id,conn=conn)
    return {'id':str(identifier),'status':'queued','reused':False}

@router.get('/admin/model-catalog')
async def catalog(actor=Depends(require('models.read'))):return [{'id':key,**value} for key,value in APPROVED.items()]

@router.post('/admin/model-installations',status_code=202)
async def install(body:Install,request:Request,actor=Depends(require('models.install'))):
    if actor.key_id or actor.auth_source=='integration':raise HTTPException(403,'interactive_session_required')
    if body.catalog_id not in APPROVED:raise HTTPException(422,'model_not_in_approved_catalog')
    return await enqueue(request,actor,'model.install',{'catalog_id':body.catalog_id},body.idempotency_key)

@router.post('/admin/model-benchmarks',status_code=202)
async def run_benchmark(body:Benchmark,request:Request,actor=Depends(require('benchmarks.run'))):
    if actor.key_id or actor.auth_source=='integration':raise HTTPException(403,'interactive_session_required')
    if not set(body.contexts)<={4096,8192} or not set(body.threads)<={12,16}:raise HTTPException(422,'benchmark_configuration_not_allowed')
    exists=await request.app.state.db.execute('SELECT id FROM moara.models WHERE id=CAST(:id AS uuid) AND installed',{'id':str(body.model_id)},one=True)
    if not exists:raise HTTPException(404,'model_not_installed')
    return await enqueue(request,actor,'model.benchmark',{'model_id':str(body.model_id),'contexts':sorted(set(body.contexts)),'threads':sorted(set(body.threads))},body.idempotency_key)

@router.get('/benchmarks')
@router.get('/models/metrics')
async def samples(request:Request,actor=Depends(require('models.read'))):
    return await request.app.state.db.execute('''SELECT b.*,m.display_name FROM moara.benchmark_samples b JOIN moara.models m ON m.id=b.model_id
        ORDER BY b.created_at DESC,b.id DESC LIMIT 300''')

JOB_COLUMNS='id,account_id,kind,status,error_code,progress,cancel_requested,attempts,created_at,started_at,updated_at,finished_at'

@router.get('/jobs')
async def jobs(request:Request,actor=Depends(require('jobs.read'))):
    where='' if actor.can('jobs.manage') else ' WHERE account_id=CAST(:account AS uuid)'
    return await request.app.state.db.execute('SELECT '+JOB_COLUMNS+' FROM moara.jobs'+where+' ORDER BY created_at DESC LIMIT 100',{'account':str(actor.user_id)})

@router.get('/jobs/{identifier}')
async def job(identifier:uuid.UUID,request:Request,actor=Depends(require('jobs.read'))):
    row=await request.app.state.db.execute('SELECT '+JOB_COLUMNS+',result FROM moara.jobs WHERE id=CAST(:id AS uuid)',{'id':str(identifier)},one=True)
    if not row or (row['account_id']!=actor.user_id and not actor.can('jobs.manage')):raise HTTPException(404,'job_not_found')
    if row['result']:
        try:row['result']=__import__('json').loads(request.app.state.settings.fernet().decrypt(row['result'].encode()))
        except Exception:raise HTTPException(503,'job_result_integrity_failure') from None
    return row

@router.post('/jobs/{identifier}/cancel')
async def cancel(identifier:uuid.UUID,request:Request,actor=Depends(require('jobs.cancel'))):
    row=await job(identifier,request,actor)
    if row['account_id']!=actor.user_id and not actor.can('jobs.manage'):raise HTTPException(404,'job_not_found')
    await request.app.state.db.execute('''UPDATE moara.jobs SET cancel_requested=true,updated_at=now(),
        status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END,
        finished_at=CASE WHEN status='queued' THEN now() ELSE finished_at END WHERE id=CAST(:id AS uuid) AND status IN ('queued','running')''',{'id':str(identifier)})
    await request.app.state.db.audit(actor,'job.cancel',identifier,request_id=request.state.request_id)
    return {'cancel_requested':True}

async def dispatch(app):
    from .worker import celery_app
    db=app.state.db
    while True:
        try:
            # A dead worker's lease must expire before another message can reclaim it.
            await db.execute('DELETE FROM moara.connector_tickets WHERE expires_at<now()')
            await db.execute("""UPDATE moara.jobs SET status=CASE WHEN attempts<3 AND NOT cancel_requested THEN 'queued' ELSE 'failed' END,
                error_code='worker_lease_expired',dispatched_at=NULL,lease_until=NULL,updated_at=now()
                WHERE status='running' AND lease_until<now()""")
            rows=await db.execute("""UPDATE moara.jobs SET dispatched_at=now() WHERE id IN
                (SELECT id FROM moara.jobs WHERE status='queued' AND NOT cancel_requested AND
                (dispatched_at IS NULL OR dispatched_at<now()-interval '60 seconds') ORDER BY created_at LIMIT 8 FOR UPDATE SKIP LOCKED) RETURNING id""")
            for row in rows:
                await asyncio.to_thread(celery_app.send_task,'moara.execute',args=[str(row['id'])],queue='moara.control')
        except asyncio.CancelledError:raise
        except Exception:
            # Protected outbox rows remain available for a later attempt.
            __import__('logging').getLogger('moara').warning('{"event":"job_dispatch_unavailable"}')
        await asyncio.sleep(3)
