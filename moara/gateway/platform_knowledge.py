"""Hybrid retrieval applies current resource ACLs before ranking and model context."""
import asyncio,base64,hashlib,json,math,uuid
from fastapi import HTTPException
from . import platform_store as store
from .platform_documents import isolated_extract

async def embeddings(app,texts):
 response=await app.state.http.post(app.state.settings.legacy_gateway+'/v1/embeddings',
  headers={'Authorization':'Bearer '+app.state.settings.llm_key},json={'model':'embedding','input':texts},timeout=90)
 if response.status_code!=200:raise HTTPException(503,'embedding_service_unavailable')
 data=response.json().get('data',[])
 if len(data)!=len(texts):raise HTTPException(503,'invalid_embedding_response')
 result=[]
 for item in sorted(data,key=lambda x:x.get('index',0)):
  vector=item.get('embedding',[])
  if len(vector)!=768 or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in vector):raise HTTPException(503,'invalid_embedding_response')
  result.append(vector)
 return result

async def blob(app,actor,identifier):
 from .document_uploads import open_blob,stream_blob
 resource,row=await open_blob(app,actor,identifier)
 raw=bytearray()
 async for part in stream_blob(app,row):raw.extend(part)
 return resource,row,bytes(raw)

async def ingest(app,actor,identifier,checkpoint):
 from .document_uploads import open_blob,stream_blob
 from pathlib import Path
 import tempfile,sys,os
 resource,row=await open_blob(app,actor,identifier)
 scratch=Path(os.getenv('MOARA_DOCUMENT_WORK_DIR','/data/document-work'))
 scratch.mkdir(parents=True,exist_ok=True,mode=0o700)
 with tempfile.TemporaryDirectory(prefix='ingest-',dir=scratch) as folder:
  source=Path(folder)/'source';output=Path(folder)/'chunks.jsonl'
  with source.open('wb') as target:
   async for part in stream_blob(app,row):
    await checkpoint()
    await asyncio.to_thread(target.write,part)
  await checkpoint()
  child=await asyncio.create_subprocess_exec(sys.executable,'-m','moara.gateway.document_extract_stream','--input',str(source),'--output',str(output),'--filename',row['filename'],stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
  try:
   if await child.wait():raise HTTPException(422,'document_extraction_failed_or_ocr_required')
  finally:
   if child.returncode is None:child.kill();await child.wait()
  await store.get(app,actor,identifier,kind='document',write=True)
  ordinal=0
  # The index remains atomic while vectors and inserts use bounded batches.
  async with app.state.db.engine.begin() as conn:
   await app.state.db.execute('DELETE FROM moara.document_chunks WHERE document_id=CAST(:id AS uuid)',{'id':str(identifier)},conn=conn)
   with output.open(encoding='utf8') as chunks:
    while True:
     batch=[]
     for _ in range(16):
      line=chunks.readline()
      if not line:break
      batch.append(json.loads(line))
     if not batch:break
     await checkpoint()
     vectors=await embeddings(app,[c['text'] for c in batch])
     for chunk,vector in zip(batch,vectors):
      await app.state.db.execute("""INSERT INTO moara.document_chunks(id,document_id,ordinal,page,content,search_terms,embedding,embedding_model,checksum)
       VALUES(CAST(:id AS uuid),CAST(:doc AS uuid),:ordinal,:page,:content,to_tsvector('portuguese',:text),CAST(:vector AS vector),'embeddinggemma-300m',:checksum)""",
       {'id':str(uuid.uuid4()),'doc':str(identifier),'ordinal':ordinal,'page':chunk['page'],'content':store.seal(app,chunk['text']),'text':chunk['text'],'vector':json.dumps(vector),'checksum':hashlib.sha256(chunk['text'].encode()).hexdigest()},conn=conn)
      ordinal+=1
   await checkpoint();await store.get(app,actor,identifier,kind='document',write=True,conn=conn)
 return {'document_id':str(identifier),'chunks':ordinal,'source_sha256':row['sha256'],'embedding_model':'embeddinggemma-300m'}

async def search(app,actor,spec):
 actor.require('knowledge.use')
 for identifier in spec.document_ids:await store.get(app,actor,identifier,kind='document')
 vector=(await embeddings(app,[spec.query]))[0]
 # Materialized eligible set prevents vector or lexical scoring over unauthorized chunks.
 rows=await app.state.db.execute("""WITH eligible AS MATERIALIZED (
 SELECT c.*,r.title FROM moara.document_chunks c JOIN moara.resources r ON r.id=c.document_id
 WHERE NOT r.archived AND """+store.VISIBLE+""" AND
 (:all_docs OR c.document_id IN (SELECT CAST(value AS uuid) FROM jsonb_array_elements_text(CAST(:ids AS jsonb))))),
 ranked AS (SELECT *,row_number() OVER(ORDER BY embedding <=> CAST(:vector AS vector),id) vr,
 row_number() OVER(ORDER BY ts_rank_cd(search_terms,plainto_tsquery('portuguese',:query)) DESC,id) lr FROM eligible)
 SELECT id,document_id,page,ordinal,content,checksum,title,1.0/(60+vr)+1.0/(60+lr) AS score
 FROM ranked ORDER BY score DESC,id LIMIT :limit""",
 {**store.access_params(actor),'ids':json.dumps([str(x) for x in spec.document_ids]),'all_docs':not spec.document_ids,
  'vector':json.dumps(vector),'query':spec.query,'limit':spec.limit})
 result=[]
 for row in rows:
  await store.get(app,actor,row['document_id'],kind='document')
  row['text']=store.unseal(app,row.pop('content'));row['citation']='['+str(len(result)+1)+']'
  result.append(row)
 return {'matches':result,'ranking':'hybrid_reciprocal_rank_fusion','reranker':'none','query':spec.query}
