"""Raw streaming uploads, encrypted segments and backward-compatible reads."""
import asyncio,base64,codecs,hashlib,uuid
from pathlib import PurePosixPath
from fastapi import APIRouter,Depends,HTTPException,Request,Query
from .auth import require
from . import platform_store as store
from .platform_documents import MEDIA

router=APIRouter(prefix='/api/v1/platform',tags=['Documents'])
SEGMENT=1024*1024

def media_for(filename):
 if not filename or len(filename)>180 or '/' in filename or '\\' in filename or filename.startswith('.') or any(ord(c)<32 for c in filename):raise HTTPException(422,'invalid_filename')
 suffix=PurePosixPath(filename).suffix.lower()
 if suffix not in MEDIA:raise HTTPException(422,'unsupported_document_type')
 return suffix,MEDIA[suffix]

@router.post('/documents/upload',status_code=201)
async def upload(request:Request,filename:str=Query(min_length=1,max_length=180),title:str=Query(min_length=1,max_length=200),group_id:uuid.UUID|None=None,actor=Depends(require('documents.use'))):
 actor.require('workspace.use')
 suffix,media=media_for(filename);app=request.app
 await store.group_allowed(app,actor,group_id)
 checksum=hashlib.sha256();size=0;ordinal=0;buffer=bytearray();prefix=bytearray()
 decoder=codecs.getincrementaldecoder('utf-8-sig')() if suffix in ('.txt','.md','.csv') else None
 cipher=app.state.settings.fernet()
 async with app.state.db.engine.begin() as conn:
  resource=await store.create(app,actor,'document',title,{'filename':filename,'upload_pending':True},group_id,conn=conn)
  async def segment(data):
   nonlocal ordinal
   encrypted=await asyncio.to_thread(cipher.encrypt,data)
   await app.state.db.execute('INSERT INTO moara.document_segments(resource_id,ordinal,content) VALUES(CAST(:id AS uuid),:ordinal,:content)',{'id':resource['id'],'ordinal':ordinal,'content':encrypted.decode()},conn=conn)
   ordinal+=1
  async for received in request.stream():
   if not received:continue
   if len(prefix)<8:prefix.extend(received[:8-len(prefix)])
   if len(prefix)>=5 and suffix=='.pdf' and not prefix.startswith(b'%PDF-'):raise HTTPException(422,'invalid_pdf')
   if len(prefix)>=4 and suffix in ('.docx','.xlsx') and not prefix.startswith(b'PK\x03\x04'):raise HTTPException(422,'invalid_office_document')
   if decoder:
    try:decoder.decode(received)
    except UnicodeError:raise HTTPException(422,'utf8_document_required') from None
   checksum.update(received);size+=len(received)
   # A transport frame is not assumed to fit a storage segment.
   for offset in range(0,len(received),SEGMENT):
    buffer.extend(received[offset:offset+SEGMENT])
    if len(buffer)>=SEGMENT:
     await segment(bytes(buffer[:SEGMENT]));del buffer[:SEGMENT]
  if not size:raise HTTPException(422,'empty_document')
  if suffix=='.pdf' and not prefix.startswith(b'%PDF-'):raise HTTPException(422,'invalid_pdf')
  if suffix in ('.docx','.xlsx') and not prefix.startswith(b'PK\x03\x04'):raise HTTPException(422,'invalid_office_document')
  if decoder:
   try:decoder.decode(b'',final=True)
   except UnicodeError:raise HTTPException(422,'utf8_document_required') from None
  if buffer:await segment(bytes(buffer))
  digest=checksum.hexdigest()
  metadata={'filename':filename,'media_type':media,'sha256':digest,'size_bytes':size}
  encrypted_metadata=store.seal(app,metadata)
  await app.state.db.execute('UPDATE moara.resources SET body=:body WHERE id=CAST(:id AS uuid)',{'body':encrypted_metadata,'id':resource['id']},conn=conn)
  await app.state.db.execute('UPDATE moara.resource_versions SET body=:body WHERE resource_id=CAST(:id AS uuid) AND version=1',{'body':encrypted_metadata,'id':resource['id']},conn=conn)
  await app.state.db.execute('INSERT INTO moara.document_blobs(resource_id,content,sha256,filename,media_type,size_bytes) VALUES(CAST(:id AS uuid),:content,:hash,:filename,:media,:size)',{'id':resource['id'],'content':store.seal(app,{'storage':'segments_v1','segments':ordinal}),'hash':digest,'filename':filename,'media':media,'size':size},conn=conn)
  await app.state.db.audit(actor,'document.upload.completed',resource['id'],conn=conn)
 return {**resource,'size_bytes':size,'sha256':digest,'storage':'encrypted_segments'}

async def open_blob(app,actor,identifier):
 resource=await store.get(app,actor,identifier,kind='document')
 row=await app.state.db.execute('SELECT * FROM moara.document_blobs WHERE resource_id=CAST(:id AS uuid)',{'id':str(identifier)},one=True)
 if not row:raise HTTPException(404,'document_blob_not_found')
 return resource,row

async def stream_blob(app,row):
 manifest=store.unseal(app,row['content']);checksum=hashlib.sha256();size=0
 if isinstance(manifest,str):
  raw=base64.b64decode(manifest,validate=True);checksum.update(raw);size=len(raw);yield raw
 elif isinstance(manifest,dict) and manifest.get('storage')=='segments_v1' and type(manifest.get('segments')) is int and manifest['segments']>0:
  last=-1;count=0;cipher=app.state.settings.fernet()
  while True:
   records=await app.state.db.execute('SELECT ordinal,content FROM moara.document_segments WHERE resource_id=CAST(:id AS uuid) AND ordinal>:last ORDER BY ordinal LIMIT 8',{'id':str(row['resource_id']),'last':last})
   if not records:break
   for record in records:
    if record['ordinal']!=last+1:raise RuntimeError('document_segment_integrity_failed')
    raw=await asyncio.to_thread(cipher.decrypt,record['content'].encode())
    if not 1<=len(raw)<=SEGMENT:raise RuntimeError('document_segment_integrity_failed')
    checksum.update(raw);size+=len(raw);last=record['ordinal'];count+=1;yield raw
  if count!=manifest['segments']:raise RuntimeError('document_segment_integrity_failed')
 else:raise RuntimeError('invalid_document_storage')
 if size!=row['size_bytes'] or checksum.hexdigest()!=row['sha256']:raise RuntimeError('document_integrity_failed')
