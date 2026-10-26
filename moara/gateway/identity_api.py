import json
import uuid
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from moara.identity import Identity,load_identity
from .database import as_json
from .auth import require,current_actor

router=APIRouter(prefix='/api/v1/identity',tags=['Institutional identity'])

class Strict(BaseModel):model_config=ConfigDict(extra='forbid')
class Draft(Strict):
    body:dict
    expected_sha256:str|None=Field(default=None,pattern=r'^[0-9a-f]{64}$')
class Publication(Strict):
    expected_active_id:uuid.UUID
    expected_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
class Answer(Strict):
    question:str=Field(min_length=1,max_length=400)
    model:str|None=Field(default=None,max_length=180)

class IdentityStore:
    def __init__(self,db):self.db=db
    async def initialize(self):
        initial=load_identity();identifier=uuid.uuid4()
        async with self.db.engine.begin() as conn:
            await self.db.execute('SELECT pg_advisory_xact_lock(42612553)',conn=conn)
            row=await self.db.execute("SELECT id FROM moara.identity_versions WHERE status='active'",one=True,conn=conn)
            if not row:
                await self.db.execute('''INSERT INTO moara.identity_versions(id,version,body,sha256,status,created_by,approved_by,approval_source,published_at)
                    VALUES(CAST(:id AS uuid),:version,CAST(:body AS jsonb),:sha,'active','deployment:nutec','deployment:nutec','user_provided_deployment_request',now())''',
                    {'id':str(identifier),'version':initial.document.version,'body':as_json(initial.value),'sha':initial.sha256},conn=conn)
    async def active(self):
        row=await self.db.execute("SELECT * FROM moara.identity_versions WHERE status='active'",one=True)
        if not row:raise HTTPException(503,'institutional_identity_not_published')
        try:
            identity=Identity(row['body'],expected_sha256=row['sha256'],publication={
                'id':str(row['id']),'status':'active','published_at':row['published_at'].isoformat(),
                'approval_source':row['approval_source'],'institutional_approver':row['body'].get('institutional_approver')})
        except ValueError:raise HTTPException(503,'institutional_identity_integrity_failure') from None
        return identity,row

@router.get('/public')
async def public_identity(request:Request):
    identity,_=await request.app.state.identity.active()
    value=identity.public()
    # Administrative actors and internal draft/audit data are not public.
    return {k:value[k] for k in ['version','institutional_id','name','product','institution','purpose','presentation','origin','origin_status',
        'origin_reference','principles','limits','declaration','signature','developer','institutional_approver','sha256','publication']}

@router.get('')
async def current(request:Request,actor=Depends(require('identity.read'))):
    identity,_=await request.app.state.identity.active();return identity.public()

@router.get('/history')
async def history(request:Request,actor=Depends(require('identity.draft'))):
    return await request.app.state.db.execute('''SELECT id,version,status,sha256,created_by,approved_by,approval_source,restored_from,created_at,published_at
        FROM moara.identity_versions ORDER BY created_at DESC LIMIT 100''')

@router.get('/versions/{identifier}')
async def version(identifier:uuid.UUID,request:Request,actor=Depends(require('identity.draft'))):
    row=await request.app.state.db.execute('SELECT * FROM moara.identity_versions WHERE id=CAST(:id AS uuid)',{'id':str(identifier)},one=True)
    if not row:raise HTTPException(404,'identity_version_not_found')
    return row

@router.post('/drafts',status_code=201)
async def draft(body:Draft,request:Request,actor=Depends(require('identity.draft'))):
    if len(as_json(body.body).encode())>64000:raise HTTPException(413,'identity_document_too_large')
    try:identity=Identity(body.body)
    except ValueError:raise HTTPException(422,'invalid_identity_document') from None
    identifier=uuid.uuid4();db=request.app.state.db
    async with db.engine.begin() as conn:
        await db.execute('''INSERT INTO moara.identity_versions(id,version,body,sha256,status,created_by)
            VALUES(CAST(:id AS uuid),:version,CAST(:body AS jsonb),:sha,'draft',:actor)''',
            {'id':str(identifier),'version':identity.document.version,'body':as_json(identity.value),'sha':identity.sha256,'actor':actor.subject},conn=conn)
        await db.audit(actor,'identity.draft.create',identifier,request_id=request.state.request_id,conn=conn)
    return {'id':str(identifier),'sha256':identity.sha256,'status':'draft'}

@router.put('/drafts/{identifier}')
async def edit(identifier:uuid.UUID,body:Draft,request:Request,actor=Depends(require('identity.draft'))):
    if len(as_json(body.body).encode())>64000:raise HTTPException(413,'identity_document_too_large')
    try:identity=Identity(body.body)
    except ValueError:raise HTTPException(422,'invalid_identity_document') from None
    db=request.app.state.db
    async with db.engine.begin() as conn:
        row=await db.execute('SELECT * FROM moara.identity_versions WHERE id=CAST(:id AS uuid) FOR UPDATE',{'id':str(identifier)},one=True,conn=conn)
        if not row:raise HTTPException(404,'identity_version_not_found')
        if row['status']!='draft':raise HTTPException(409,'published_identity_is_immutable')
        if row['sha256']!=body.expected_sha256:raise HTTPException(409,'identity_draft_changed')
        new_id=uuid.uuid4()
        await db.execute("UPDATE moara.identity_versions SET status='draft_history' WHERE id=CAST(:id AS uuid)",{'id':str(identifier)},conn=conn)
        await db.execute('''INSERT INTO moara.identity_versions(id,version,body,sha256,status,created_by,parent_id)
            VALUES(CAST(:id AS uuid),:version,CAST(:body AS jsonb),:sha,'draft',:actor,CAST(:parent AS uuid))''',
            {'id':str(new_id),'body':as_json(identity.value),'sha':identity.sha256,'version':identity.document.version,
                'actor':actor.subject,'parent':str(identifier)},conn=conn)
        await db.audit(actor,'identity.draft.edit',new_id,request_id=request.state.request_id,conn=conn)
    return {'id':str(new_id),'sha256':identity.sha256,'status':'draft','parent_id':str(identifier)}

@router.post('/drafts/{identifier}/publish')
async def publish(identifier:uuid.UUID,body:Publication,request:Request,actor=Depends(require('identity.publish'))):
    db=request.app.state.db
    async with db.engine.begin() as conn:
        await db.execute('SELECT pg_advisory_xact_lock(42612553)',conn=conn)
        active=await db.execute("SELECT id FROM moara.identity_versions WHERE status='active' FOR UPDATE",one=True,conn=conn)
        row=await db.execute("SELECT * FROM moara.identity_versions WHERE id=CAST(:id AS uuid) FOR UPDATE",{'id':str(identifier)},one=True,conn=conn)
        if not row or row['status']!='draft':raise HTTPException(409,'identity_draft_not_available')
        if not active or active['id']!=body.expected_active_id or row['sha256']!=body.expected_sha256:raise HTTPException(409,'identity_publication_changed')
        Identity(row['body'],expected_sha256=row['sha256'])
        await db.execute("UPDATE moara.identity_versions SET status='superseded' WHERE status='active'",conn=conn)
        await db.execute("""UPDATE moara.identity_versions SET status='active',approved_by=:actor,approval_source='authorized_identity_publication',published_at=now()
            WHERE id=CAST(:id AS uuid)""",{'id':str(identifier),'actor':actor.subject},conn=conn)
        await db.audit(actor,'identity.publish',identifier,request_id=request.state.request_id,conn=conn)
    return {'id':str(identifier),'status':'active','sha256':row['sha256']}

@router.post('/versions/{identifier}/restore')
async def restore(identifier:uuid.UUID,body:Publication,request:Request,actor=Depends(require('identity.publish'))):
    db=request.app.state.db;new_id=uuid.uuid4()
    async with db.engine.begin() as conn:
        await db.execute('SELECT pg_advisory_xact_lock(42612553)',conn=conn)
        active=await db.execute("SELECT id FROM moara.identity_versions WHERE status='active' FOR UPDATE",one=True,conn=conn)
        previous=await db.execute("SELECT * FROM moara.identity_versions WHERE id=CAST(:id AS uuid) AND status='superseded'",{'id':str(identifier)},one=True,conn=conn)
        if not previous or not active:raise HTTPException(404,'published_identity_version_not_found')
        if active['id']!=body.expected_active_id or previous['sha256']!=body.expected_sha256:raise HTTPException(409,'identity_publication_changed')
        Identity(previous['body'],expected_sha256=previous['sha256'])
        await db.execute("UPDATE moara.identity_versions SET status='superseded' WHERE status='active'",conn=conn)
        await db.execute('''INSERT INTO moara.identity_versions(id,version,body,sha256,status,created_by,approved_by,approval_source,restored_from,published_at)
            VALUES(CAST(:id AS uuid),:version,CAST(:body AS jsonb),:sha,'active',:actor,:actor,'authorized_identity_restore',CAST(:previous AS uuid),now())''',
            {'id':str(new_id),'version':previous['version'],'body':as_json(previous['body']),'sha':previous['sha256'],'actor':actor.subject,'previous':str(identifier)},conn=conn)
        await db.audit(actor,'identity.restore',identifier,request_id=request.state.request_id,conn=conn)
    return {'id':str(new_id),'status':'active','sha256':previous['sha256'],'restored_from':str(identifier)}

@router.post('/answer')
async def answer(body:Answer,request:Request,actor=Depends(require('identity.read'))):
    identity,_=await request.app.state.identity.active()
    # Never accept model or source claims from a browser as factual metadata.
    from .institutional import answer as resolve
    result=await resolve(identity,body.question,request,actor)
    if not result:return {'matched':False,'identity_version':identity.document.version}
    return {'matched':True,**result}
