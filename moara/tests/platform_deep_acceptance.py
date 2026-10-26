import asyncio,base64,hashlib,io,json,subprocess,tempfile,uuid,zlib
from pathlib import Path
from types import SimpleNamespace
import httpx
from fastapi import HTTPException
from moara.gateway.settings import Settings
from moara.gateway.database import Database
from moara.gateway.auth import Auth
from moara.gateway import platform_store as store,platform_knowledge as knowledge
from moara.gateway.platform_contracts import SearchRequest
from moara.gateway.platform_documents import isolated_extract
checks=[]
def check(name,value):
 checks.append({'name':name,'passed':bool(value)})
 if not value:raise AssertionError(name)
async def main():
 settings=Settings.load();db=Database(settings)
 async with httpx.AsyncClient(trust_env=False) as http:
  auth=Auth(settings,db,http);app=SimpleNamespace(state=SimpleNamespace(settings=settings,db=db,auth=auth,http=http))
  arow=await db.execute("SELECT * FROM moara.accounts WHERE email='alice@platform.invalid'",one=True)
  brow=await db.execute("SELECT * FROM moara.accounts WHERE email='bob@platform.invalid'",one=True)
  a=await auth.from_row(arow);b=await auth.from_row(brow)
  calls=[]
  async def fixture_embeddings(app,texts):
   calls.extend(texts);return [[1.0]+[0.0]*767 for text in texts]
  knowledge.embeddings=fixture_embeddings
  docs=[]
  for actor,title,text in ((a,'Fonte A','O prazo fictício da equipe Alfa é cinco dias.'),(b,'Fonte B','SEGREDO_FICTICIO_B Não deve aparecer para Alfa.')):
   raw=text.encode();r=await store.create(app,actor,'document',title,{'filename':'fixture.txt'})
   await db.execute("""INSERT INTO moara.document_blobs(resource_id,content,sha256,filename,media_type,size_bytes)
    VALUES(CAST(:id AS uuid),:content,:sha,'fixture.txt','text/plain',:size)""",
    {'id':r['id'],'content':store.seal(app,base64.b64encode(raw).decode()),'sha':hashlib.sha256(raw).hexdigest(),'size':len(raw)})
   async def checkpoint():return actor
   result=await knowledge.ingest(app,actor,r['id'],checkpoint);check('ingest_'+title,result['chunks']>0);docs.append(r['id'])
  result=await knowledge.search(app,a,SearchRequest(query='prazo fictício'))
  check('hybrid_real_pgvector',any(str(m['document_id'])==docs[0] for m in result['matches']))
  check('acl_before_context',all(str(m['document_id'])!=docs[1] and 'SEGREDO_FICTICIO_B' not in m['text'] for m in result['matches']))
  before=len(calls)
  try:await knowledge.search(app,a,SearchRequest(query='segredo',document_ids=[docs[1]]))
  except HTTPException as exc:check('explicit_forbidden_source_denied',exc.status_code==404)
  else:check('explicit_forbidden_source_denied',False)
  check('forbidden_source_before_embeddings',len(calls)==before)
  a.key_id=uuid.uuid4();a.allowed_sources=()
  result=await knowledge.search(app,a,SearchRequest(query='prazo'))
  check('api_key_empty_source_scope',not result['matches'])
  a.allowed_sources=(docs[0],)
  result=await knowledge.search(app,a,SearchRequest(query='prazo'))
  check('api_key_explicit_source_scope',len(result['matches'])==1)
  await auth.close()
 await db.dispose()
asyncio.run(main())

def pdf(objects):
 out=bytearray(b'%PDF-1.4\n');offsets=[0]
 for i,obj in enumerate(objects,1):
  offsets.append(len(out));out.extend(str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n')
 start=len(out);out.extend(('xref\n0 '+str(len(offsets))+'\n0000000000 65535 f \n').encode())
 for offset in offsets[1:]:out.extend(f'{offset:010} 00000 n \n'.encode())
 out.extend(('trailer\n<< /Size '+str(len(offsets))+' /Root 1 0 R >>\nstartxref\n'+str(start)+'\n%%EOF').encode());return bytes(out)
def stream(raw,extra=b''):return b'<< /Length '+str(len(raw)).encode()+b' '+extra+b' >>\nstream\n'+raw+b'\nendstream'
base=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>']
digital=pdf(base+[b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',stream(b'BT /F1 24 Tf 30 100 Td (SYNTHETIC OCR TEST 42) Tj ET')])
check('digital_pdf',any('SYNTHETIC' in c['text'] for c in isolated_extract(digital,'digital.pdf')))
with tempfile.TemporaryDirectory() as folder:
 p=Path(folder)/'digital.pdf';p.write_bytes(digital)
 subprocess.run(['pdftoppm','-singlefile','-r','120',str(p),str(Path(folder)/'page')],check=True,capture_output=True)
 data=(Path(folder)/'page.ppm').read_bytes();parts=data.split(b'\n',3);width,height=map(int,parts[1].split());raw=parts[3]
 image=stream(zlib.compress(raw),f'/Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode'.encode())
 scanned=pdf(base+[b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 200] /Resources << /XObject << /I1 4 0 R >> >> /Contents 5 0 R >>',image,stream(b'q 600 0 0 200 0 0 cm /I1 Do Q')])
 chunks=isolated_extract(scanned,'scanned.pdf')
 check('ocr_real_tesseract',any('SYNTHETIC' in c['text'] and c.get('ocr') for c in chunks))
print('DEEP_REPORT='+json.dumps({'checks':checks,'embedding_fixture':'deterministic_test_only','actual_extraction_and_database':True,'synthetic_only':True}))
