"""Explicit, digest-bound execution approval; the API has no Docker socket."""
import json,os,uuid
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import Field
from .auth import require
from .platform_contracts import Approval,Strict,RunCreate
from . import platform_store as store,platform_runs as runs
router=APIRouter(prefix='/api/v1/platform/projects',tags=['MOARA DEV'])
class Accept(Approval):
 run_id:uuid.UUID
@router.get('/{identifier}/review')
async def review(identifier:uuid.UUID,request:Request,actor=Depends(require('development.use'))):
 row=await store.get(request.app,actor,identifier,kind='project',write=True);files=row['body'].get('files',{})
 return {'version':row['version'],'digest':store.digest(files),'files':files,'execution_enabled':os.getenv('MOARA_SANDBOX_READY')=='true'}
@router.post('/{identifier}/accept')
async def accept(identifier:uuid.UUID,body:Accept,request:Request,actor=Depends(require('development.use'))):
 row=await store.get(request.app,actor,identifier,kind='project',write=True)
 proposal=await request.app.state.db.execute("""SELECT result FROM moara.platform_runs WHERE id=CAST(:id AS uuid)
 AND resource_id=CAST(:project AS uuid) AND account_id=CAST(:actor AS uuid) AND status='completed' AND kind='project.generate'""",
 {'id':str(body.run_id),'project':str(identifier),'actor':str(actor.user_id)},one=True)
 if not proposal:raise HTTPException(404,'proposal_not_found')
 result=store.unseal(request.app,proposal['result'])
 if result['project_version']!=body.version or store.digest(result['files'])!=body.digest:raise HTTPException(409,'proposal_changed')
 new={**row['body'],'files':result['files'],'review':{'accepted_by':str(actor.user_id),'proposal_id':str(body.run_id),'digest':body.digest}}
 return await store.update(request.app,actor,identifier,row['title'],new,row['group_id'],body.version)
@router.post('/{identifier}/execute',status_code=202)
async def execute(identifier:uuid.UUID,body:Approval,request:Request,actor=Depends(require('development.execute'))):
 if actor.key_id or actor.auth_source=='integration':raise HTTPException(403,'interactive_approval_required')
 if os.getenv('MOARA_SANDBOX_READY')!='true':raise HTTPException(503,'sandbox_not_enabled')
 row=await store.get(request.app,actor,identifier,kind='project',write=True)
 files=row['body'].get('files',{})
 if row['version']!=body.version or store.digest(files)!=body.digest:raise HTTPException(409,'project_approval_changed')
 language=row['body'].get('language','python')
 entry='main.py' if language in ('python','fastapi') else 'main.ts'
 if entry not in files:raise HTTPException(422,'sandbox_entrypoint_required')
 queued=await runs.enqueue(request.app,actor,RunCreate(operation='project.execute',resource_id=identifier,input={},idempotency_key='execute:'+store.digest({'id':str(identifier),'version':body.version,'digest':body.digest})))
 await request.app.state.db.execute("""UPDATE moara.platform_runs SET approved_by=CAST(:actor AS uuid),approved_at=now(),approval_digest=:digest
 WHERE id=CAST(:id AS uuid) AND status='queued'""",{'id':queued['id'],'actor':str(actor.user_id),'digest':body.digest})
 await request.app.state.db.audit(actor,'project.execution.approved',queued['id'])
 return queued
