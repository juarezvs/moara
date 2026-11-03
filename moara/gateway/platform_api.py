"""Institutional workspace APIs; authorization and encryption are centralized."""
import asyncio,base64,hashlib,json,uuid
from .platform_exports import isolated as export_isolated
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import Response,StreamingResponse
from .auth import require
from . import platform_store as store,platform_runs as runs,platform_knowledge as knowledge
from .platform_contracts import ResourceCreate,ResourceUpdate,RunCreate,Upload,SearchRequest,TemplateRender,DatasetQuery,Revision,AGENTS,OPERATIONS
from .platform_documents import decode_upload,render_template,aggregate,export_csv,docx_export

router=APIRouter(prefix='/api/v1/platform',tags=['Institutional platform'])
@router.get('/agents')
async def agents(actor=Depends(require('workspace.use'))):return [{**a,'preferred_model':'auto_authorized','execution_policy':'propose_or_fixed_tool_only','requires_approval_for_code':True} for a in AGENTS]
@router.get('/groups')
async def groups(request:Request,actor=Depends(require('workspace.use'))):
 return await request.app.state.db.execute('SELECT g.id,g.name FROM moara.groups g JOIN moara.group_members m ON m.group_id=g.id WHERE m.account_id=CAST(:actor AS uuid) ORDER BY g.name',{'actor':str(actor.user_id)})
@router.get('/resources')
async def listing(request:Request,kind:str|None=None,actor=Depends(require('workspace.use'))):
 if kind and kind not in {'document','prompt','template','assistant','project','case','workflow','dashboard'}:raise HTTPException(422,'invalid_kind')
 return await request.app.state.db.execute('SELECT r.id,r.kind,r.title,r.version,r.owner_id,r.group_id,r.updated_at FROM moara.resources r WHERE NOT r.archived AND '+store.VISIBLE+' AND (CAST(:kind AS text) IS NULL OR r.kind=:kind) ORDER BY r.updated_at DESC LIMIT 200',{**store.access_params(actor),'kind':kind})
@router.post('/resources',status_code=201)
async def create(body:ResourceCreate,request:Request,actor=Depends(require('workspace.use'))):
 if body.kind=='document':raise HTTPException(422,'use_document_upload')
 return await store.create(request.app,actor,body.kind,body.title,body.body,body.group_id)
@router.get('/resources/{identifier}')
async def read(identifier:uuid.UUID,request:Request,actor=Depends(require('workspace.use'))):
 return await store.get(request.app,actor,identifier)
@router.put('/resources/{identifier}')
async def update(identifier:uuid.UUID,body:ResourceUpdate,request:Request,actor=Depends(require('workspace.use'))):
 original=await store.get(request.app,actor,identifier,write=True)
 if original['kind']=='document' and body.body!=original['body']:raise HTTPException(422,'document_content_immutable')
 return await store.update(request.app,actor,identifier,body.title,body.body,body.group_id,body.version)
@router.post('/resources/{identifier}/archive')
async def archive(identifier:uuid.UUID,body:Revision,request:Request,actor=Depends(require('workspace.use'))):
 async with request.app.state.db.engine.begin() as conn:
  row=await store.get(request.app,actor,identifier,write=True,conn=conn,lock=True)
  if row['version']!=body.version:raise HTTPException(409,'resource_version_conflict')
  await request.app.state.db.execute('UPDATE moara.resources SET archived=true,version=version+1,updated_at=now() WHERE id=CAST(:id AS uuid)',{'id':str(identifier)},conn=conn)
  await request.app.state.db.audit(actor,'resource.archived',identifier,conn=conn)
 return {'archived':True}
@router.get('/resources/{identifier}/versions')
async def versions(identifier:uuid.UUID,request:Request,actor=Depends(require('workspace.use'))):
 await store.get(request.app,actor,identifier)
 return await request.app.state.db.execute('SELECT version,title,author_id,created_at FROM moara.resource_versions WHERE resource_id=CAST(:id AS uuid) ORDER BY version DESC LIMIT 100',{'id':str(identifier)})
@router.post('/documents',status_code=201)
async def upload(body:Upload,request:Request,actor=Depends(require('documents.use'))):
 actor.require('workspace.use');raw,media=decode_upload(body.filename,body.content_base64);checksum=hashlib.sha256(raw).hexdigest()
 async with request.app.state.db.engine.begin() as conn:
  resource=await store.create(request.app,actor,'document',body.title,{'filename':body.filename,'media_type':media,'sha256':checksum,'size_bytes':len(raw)},body.group_id,conn=conn)
  await request.app.state.db.execute("""INSERT INTO moara.document_blobs(resource_id,content,sha256,filename,media_type,size_bytes)
  VALUES(CAST(:id AS uuid),:content,:hash,:filename,:media,:size)""",{'id':resource['id'],'content':store.seal(request.app,body.content_base64),'hash':checksum,'filename':body.filename,'media':media,'size':len(raw)},conn=conn)
 return resource
@router.get('/documents/{identifier}/download')
async def download(identifier:uuid.UUID,request:Request,actor=Depends(require('documents.use'))):
 from .document_uploads import open_blob,stream_blob
 _,row=await open_blob(request.app,actor,identifier)
 await request.app.state.db.audit(actor,'document.downloaded',identifier)
 return StreamingResponse(stream_blob(request.app,row),media_type='application/octet-stream',headers={'Content-Length':str(row['size_bytes']),'Content-Disposition':'attachment; filename="document'+('.'+row['filename'].rsplit('.',1)[-1])+'"'})
@router.get('/documents/{identifier}/chunks')
async def chunks(identifier:uuid.UUID,request:Request,actor=Depends(require('knowledge.use'))):
 await store.get(request.app,actor,identifier,kind='document')
 rows=await request.app.state.db.execute('SELECT id,ordinal,page,checksum,content FROM moara.document_chunks WHERE document_id=CAST(:id AS uuid) ORDER BY ordinal LIMIT 1200',{'id':str(identifier)})
 for row in rows:row['text']=store.unseal(request.app,row.pop('content'))
 return rows
@router.post('/knowledge/search')
async def search(body:SearchRequest,request:Request,actor=Depends(require('knowledge.use'))):
 return await knowledge.search(request.app,actor,body)
@router.post('/templates/{identifier}/render')
async def render(identifier:uuid.UUID,body:TemplateRender,request:Request,actor=Depends(require('documents.use'))):
 row=await store.get(request.app,actor,identifier,kind='template')
 if row['version']!=body.version:raise HTTPException(409,'resource_version_conflict')
 data=row['body']
 if data.get('document_id'):
  _,source,raw=await knowledge.blob(request.app,actor,data['document_id'])
  if not source['filename'].lower().endswith('.docx'):raise HTTPException(422,'docx_template_required')
  result=await asyncio.to_thread(export_isolated,'docx',{'source':base64.b64encode(raw).decode(),'variables':data.get('variables',[]),'fields':body.fields})
 else:
  text=render_template(data.get('text',''),data.get('variables',[]),body.fields)
  result={'text':text,'docx_base64':base64.b64encode(docx_export(text)).decode()}
 try:result.update(await asyncio.to_thread(export_isolated,'pdf',{'text':result['text']}))
 except HTTPException:result['pdf_available']=False
 await store.references(request.app,actor,data)
 await request.app.state.db.audit(actor,'template.rendered',identifier)
 return {**result,'template_id':str(identifier),'version':row['version'],'draft':True,'pdf_layout':'text_review_copy'}
@router.post('/analytics/query')
async def analytics(body:DatasetQuery,request:Request,actor=Depends(require('data.query'))):
 _,row,raw=await knowledge.blob(request.app,actor,body.document_id)
 if row['media_type']!='text/csv':raise HTTPException(422,'csv_dataset_required')
 result=aggregate(raw,body);await request.app.state.db.audit(actor,'analytics.queried',body.document_id)
 return {**result,'csv':export_csv(result)}
@router.post('/runs',status_code=202)
async def enqueue(body:RunCreate,request:Request,actor=Depends(require('workspace.use'))):
 if body.operation=='project.execute':raise HTTPException(403,'interactive_approval_required')
 return await runs.enqueue(request.app,actor,body)
@router.get('/runs')
async def jobs(request:Request,actor=Depends(require('jobs.read'))):
 return await request.app.state.db.execute('SELECT id,resource_id,kind,status,error_code,created_at,finished_at FROM moara.platform_runs WHERE account_id=CAST(:actor AS uuid) ORDER BY created_at DESC LIMIT 100',{'actor':str(actor.user_id)})
@router.get('/runs/{identifier}')
async def job(identifier:uuid.UUID,request:Request,actor=Depends(require('jobs.read'))):
 row=await request.app.state.db.execute('SELECT * FROM moara.platform_runs WHERE id=CAST(:id AS uuid) AND account_id=CAST(:actor AS uuid)',{'id':str(identifier),'actor':str(actor.user_id)},one=True)
 if not row:raise HTTPException(404,'job_not_found')
 actor.require(OPERATIONS[row['kind']][1])
 if row['resource_id']:await store.get(request.app,actor,row['resource_id'])
 for source in row['source_ids']:await store.get(request.app,actor,source)
 row.pop('payload');row['result']=store.unseal(request.app,row['result']) if row['result'] else None
 return row
@router.post('/runs/{identifier}/cancel')
async def cancel(identifier:uuid.UUID,request:Request,actor=Depends(require('jobs.cancel'))):
 await request.app.state.db.execute("""UPDATE moara.platform_runs SET cancel_requested=true,
 status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END,updated_at=now()
 WHERE id=CAST(:id AS uuid) AND account_id=CAST(:actor AS uuid) AND status IN ('queued','running')""",{'id':str(identifier),'actor':str(actor.user_id)})
 await request.app.state.db.audit(actor,'platform.run.cancelled',identifier)
 return {'cancel_requested':True}

@router.get('/runs/{identifier}/export')
async def export_run(identifier:uuid.UUID,request:Request,format:str='docx',actor=Depends(require('documents.use'))):
 actor.require('jobs.read');row=await job(identifier,request,actor)
 text=(row.get('result') or {}).get('text')
 if not isinstance(text,str):raise HTTPException(422,'text_result_required')
 if format=='docx':raw=docx_export(text);media='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
 elif format=='pdf':
  result=await asyncio.to_thread(export_isolated,'pdf',{'text':text});raw=base64.b64decode(result['pdf_base64']);media='application/pdf'
 else:raise HTTPException(422,'unsupported_export_format')
 await job(identifier,request,actor)
 return Response(raw,media_type=media,headers={'Content-Disposition':'attachment; filename="moara-rascunho.'+format+'"'})
