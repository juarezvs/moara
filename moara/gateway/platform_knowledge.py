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
 resource=await store.get(app,actor,identifier,kind='document')
 row=await app.state.db.execute('SELECT * FROM moara.document_blobs WHERE resource_id=CAST(:id AS uuid)',{'id':str(identifier)},one=True)
 if not row:raise HTTPException(404,'document_blob_not_found')
 return resource,row,base64.b64decode(store.unseal(app,row['content']))

async def ingest(app,actor,identifier,checkpoint):
 resource,row,raw=await blob(app,actor,identifier)
 chunks=await asyncio.to_thread(isolated_extract,raw,row['filename']);vectors=[]
 for offset in range(0,len(chunks),16):
  await checkpoint()
  vectors.extend(await embeddings(app,[c['text'] for c in chunks[offset:offset+16]]))
 await checkpoint();await store.get(app,actor,identifier,kind='document',write=True)
 async with app.state.db.engine.begin() as conn:
  await app.state.db.execute('DELETE FROM moara.document_chunks WHERE document_id=CAST(:id AS uuid)',{'id':str(identifier)},conn=conn)
  for ordinal,(chunk,vector) in enumerate(zip(chunks,vectors)):
   await app.state.db.execute("""INSERT INTO moara.document_chunks(id,document_id,ordinal,page,content,search_terms,embedding,embedding_model,checksum)
    VALUES(CAST(:id AS uuid),CAST(:doc AS uuid),:ordinal,:page,:content,to_tsvector('portuguese',:text),CAST(:vector AS vector),'embeddinggemma-300m',:checksum)""",
    {'id':str(uuid.uuid4()),'doc':str(identifier),'ordinal':ordinal,'page':chunk['page'],
     'content':store.seal(app,chunk['text']),'text':chunk['text'],'vector':json.dumps(vector),
     'checksum':hashlib.sha256(chunk['text'].encode()).hexdigest()},conn=conn)
 return {'document_id':str(identifier),'chunks':len(chunks),'source_sha256':row['sha256'],'embedding_model':'embeddinggemma-300m'}

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
