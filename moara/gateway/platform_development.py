"""Explicit, digest-bound execution approval; the API has no Docker socket."""
import asyncio,base64,json,os,uuid
from fastapi.responses import Response
from .platform_exports import isolated as export_isolated
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import Field
from .auth import require
from .platform_contracts import Approval,Strict,RunCreate
from . import platform_store as store,platform_runs as runs
from . import project_tree
router=APIRouter(prefix='/api/v1/platform/projects',tags=['MOARA DEV'])
class Accept(Approval):
 run_id:uuid.UUID
class FileOperations(Strict):
 version:int=Field(ge=1)
 operations:list[dict]=Field(min_length=1,max_length=64)
class Restore(Strict):
 version:int=Field(ge=1)
 source_version:int=Field(ge=1)
class ProjectTask(Strict):
 version:int=Field(ge=1)
 instructions:str=Field(min_length=2,max_length=4000)
 allow_delete:bool=False
def interactive_files(actor):
 if actor.key_id or not actor.session_id or actor.auth_source=='integration':raise HTTPException(403,'interactive_session_required')
 actor.require('workspace.use')
@router.get('/{identifier}/files')
async def project_files(identifier:uuid.UUID,request:Request,actor=Depends(require('development.use'))):
 interactive_files(actor)
 row=await store.get(request.app,actor,identifier,kind='project',write=True)
 return {'version':row['version'],**project_tree.tree(row['body'])}
@router.post('/{identifier}/files')
async def change_files(identifier:uuid.UUID,body:FileOperations,request:Request,actor=Depends(require('development.use'))):
 interactive_files(actor)
 row=await store.get(request.app,actor,identifier,kind='project',write=True)
 if row['version']!=body.version:raise HTTPException(409,'resource_version_conflict')
 new=project_tree.apply(row['body'],body.operations)
 return await store.update(request.app,actor,identifier,row['title'],new,row['group_id'],body.version)
@router.post('/{identifier}/restore')
async def restore_files(identifier:uuid.UUID,body:Restore,request:Request,actor=Depends(require('development.use'))):
 interactive_files(actor)
 row=await store.get(request.app,actor,identifier,kind='project',write=True)
 old=await request.app.state.db.execute('SELECT body FROM moara.resource_versions WHERE resource_id=CAST(:id AS uuid) AND version=:version',
  {'id':str(identifier),'version':body.source_version},one=True)
 if not old:raise HTTPException(404,'resource_version_not_found')
 previous=store.unseal(request.app,old['body'])
 new={**row['body'],'files':previous.get('files',{}),'directories':previous.get('directories',[])}
 return await store.update(request.app,actor,identifier,row['title'],new,row['group_id'],body.version)
@router.post('/{identifier}/assistant')
async def edit_with_assistant(identifier:uuid.UUID,body:ProjectTask,request:Request,actor=Depends(require('development.use'))):
 from .project_agent import run
 interactive_files(actor);actor.require('chat.use')
 row=await store.get(request.app,actor,identifier,kind='project',write=True)
 if row['version']!=body.version:raise HTTPException(409,'resource_version_conflict')
 try:new,operations,text=await asyncio.wait_for(run(request.app,actor,row['body'],body.instructions,body.allow_delete),timeout=540)
 except asyncio.TimeoutError:raise HTTPException(504,'project_agent_timeout_no_changes_saved') from None
 if await request.is_disconnected():raise HTTPException(409,'project_agent_client_disconnected')
 # A changed role or expired session during inference must prevent the commit.
 fresh=await request.app.state.auth.authenticate(request)
 interactive_files(fresh);fresh.require('development.use');fresh.require('chat.use')
 if fresh.user_id!=actor.user_id:raise HTTPException(403,'job_identity_revoked')
 saved=await store.update(request.app,fresh,identifier,row['title'],new,row['group_id'],body.version) if operations else {'id':str(identifier),'version':body.version}
 return {**saved,'text':text,'operations':operations,'saved':bool(operations),'executed':False}
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

@router.get('/{identifier}/git.bundle')
async def export_git(identifier:uuid.UUID,request:Request,actor=Depends(require('development.use'))):
 await store.get(request.app,actor,identifier,kind='project',write=True)
 versions=await request.app.state.db.execute('SELECT version,body FROM moara.resource_versions WHERE resource_id=CAST(:id AS uuid) ORDER BY version DESC LIMIT 100',{'id':str(identifier)})
 payload=[{'version':r['version'],'files':store.unseal(request.app,r['body']).get('files',{})} for r in reversed(versions)]
 result=await asyncio.to_thread(export_isolated,'git',{'versions':payload})
 await store.get(request.app,actor,identifier,kind='project',write=True)
 await request.app.state.db.audit(actor,'project.git.exported',identifier)
 return Response(base64.b64decode(result['bundle_base64']),media_type='application/octet-stream',
  headers={'Content-Disposition':'attachment; filename="moara-project.bundle"','X-Moara-Exported-Versions':str(len(payload))})
