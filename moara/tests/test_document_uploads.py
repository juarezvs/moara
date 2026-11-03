import asyncio,base64,hashlib,io,tempfile,unittest,uuid,zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from cryptography.fernet import Fernet,InvalidToken
from fastapi import HTTPException
from moara.gateway import document_uploads as u,platform_documents as d,document_extract_stream as x
from moara.gateway.platform_contracts import Upload

class DB:
 def __init__(self):self.parts=[];self.blob=None;self.engine=self;self.rolled_back=False
 def begin(self):return self
 async def __aenter__(self):return self
 async def __aexit__(self,kind,*args):
  if kind:self.parts=[];self.blob=None;self.rolled_back=True
 async def execute(self,sql,p=None,**kwargs):
  if sql.startswith('INSERT INTO moara.document_segments'):self.parts.append({'ordinal':p['ordinal'],'content':p['content']})
  if sql.startswith('INSERT INTO moara.document_blobs'):self.blob=p
  if sql.startswith('SELECT ordinal,content'):return [v for v in self.parts if v['ordinal']>p['last']][:8]
 async def audit(self,*a,**kw):pass

class UploadTests(unittest.IsolatedAsyncioTestCase):
 def app(self):
  db=DB();cipher=Fernet(Fernet.generate_key())
  return SimpleNamespace(state=SimpleNamespace(db=db,settings=SimpleNamespace(fernet=lambda:cipher)))
 async def send(self,app,parts,filename='qa.pdf'):
  async def stream():
   for part in parts:
    if isinstance(part,BaseException):raise part
    yield part
  request=SimpleNamespace(app=app,stream=stream);actor=SimpleNamespace(require=lambda p:None)
  with patch.object(u.store,'create',AsyncMock(return_value={'id':str(uuid.uuid4()),'version':1})),patch.object(u.store,'group_allowed',AsyncMock()):
   return await u.upload(request,filename,'Upload QA',None,actor)
 async def test_file_above_former_ceiling_is_segmented_encrypted_and_exactly_replayable(self):
  app=self.app();raw=b'%PDF-'+b'x'*(5*1024*1024+123)
  result=await self.send(app,[raw[:7],raw[7:]])
  self.assertEqual(result['size_bytes'],len(raw));self.assertEqual(result['sha256'],hashlib.sha256(raw).hexdigest())
  self.assertGreater(len(app.state.db.parts),4);self.assertTrue(all('%PDF-' not in p['content'] for p in app.state.db.parts))
  b=app.state.db.blob;row={'resource_id':b['id'],'content':b['content'],'sha256':b['hash'],'size_bytes':b['size']}
  decoded=b''.join([p async for p in u.stream_blob(app,row)]);self.assertEqual(decoded,raw)
 async def test_abort_rolls_back_segments_instead_of_publishing_a_partial_document(self):
  app=self.app()
  with self.assertRaises(asyncio.CancelledError):await self.send(app,[b'%PDF-'+b'x'*u.SEGMENT,asyncio.CancelledError()])
  self.assertTrue(app.state.db.rolled_back);self.assertEqual(app.state.db.parts,[])
 async def test_invalid_utf8_and_empty_body_do_not_create_completed_blob(self):
  for parts in [[],[b'abc',b'\xff']]:
   app=self.app()
   with self.assertRaises(HTTPException):await self.send(app,parts,'qa.txt')
   self.assertTrue(app.state.db.rolled_back);self.assertIsNone(app.state.db.blob)
 async def test_utf8_character_may_cross_network_frames(self):
  app=self.app();raw='Ação'.encode('utf8');result=await self.send(app,[raw[:2],raw[2:3],raw[3:]],'qa.txt')
  self.assertEqual(result['sha256'],hashlib.sha256(raw).hexdigest())
 async def test_original_base64_documents_remain_readable(self):
  app=self.app();raw=b'previous document';row={'content':u.store.seal(app,base64.b64encode(raw).decode()),'size_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
  self.assertEqual(b''.join([part async for part in u.stream_blob(app,row)]),raw)
 async def test_access_is_checked_before_reading_any_document_payload(self):
  app=self.app();app.state.db.execute=AsyncMock()
  with patch.object(u.store,'get',AsyncMock(side_effect=HTTPException(404,'resource_not_found'))):
   with self.assertRaises(HTTPException):await u.open_blob(app,None,uuid.uuid4())
  self.assertEqual(app.state.db.execute.await_count,0)
 async def test_missing_segment_cannot_silently_shorten_download(self):
  app=self.app();result=await self.send(app,[b'%PDF-'+b'x'*u.SEGMENT*2]);app.state.db.parts.pop(1);b=app.state.db.blob
  row={'resource_id':result['id'],'content':b['content'],'size_bytes':b['size'],'sha256':b['hash']}
  with self.assertRaises(RuntimeError):[part async for part in u.stream_blob(app,row)]
 async def test_real_asgi_middleware_streams_large_upload_but_keeps_json_request_guard(self):
  import httpx
  from moara.gateway.api import create_app
  app=create_app(SimpleNamespace(version='qa'));fake=self.app();app.state.db=fake.state.db;app.state.settings=fake.state.settings
  app.state.auth=SimpleNamespace(authenticate=AsyncMock(return_value=SimpleNamespace(require=lambda p:None)))
  raw=b'%PDF-'+b'x'*10*1024**2
  with patch.object(u.store,'create',AsyncMock(return_value={'id':str(uuid.uuid4()),'version':1})),patch.object(u.store,'group_allowed',AsyncMock()):
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://localhost:8443') as client:
    result=await client.post('/moara/api/v1/platform/documents/upload?filename=qa.pdf&title=QA',content=raw)
    self.assertEqual(result.status_code,201,result.text)
    result=await client.post('/moara/api/v1/platform/documents',content=raw)
    self.assertEqual(result.status_code,413)

class ExtractionTests(unittest.TestCase):
 def test_compatibility_contract_no_longer_rejects_four_mebibytes(self):
  raw=b'a'*(4194304+1);encoded=base64.b64encode(raw).decode();body=Upload(filename='qa.txt',title='QA',content_base64=encoded)
  self.assertEqual(d.decode_upload(body.filename,body.content_base64)[0],raw)
 def test_large_text_is_extracted_past_old_text_and_chunk_caps(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'large.txt';path.write_text('Public synthetic text. '*90000+'FINAL_SYNTHETIC_MARKER',encoding='utf8')
   count=0;found=False
   for row in x.extract_file(path,'large.txt'):count+=1;found|='FINAL_SYNTHETIC_MARKER' in row['text']
   self.assertGreater(count,1200);self.assertTrue(found)
 def test_document_media_size_does_not_require_loading_it_to_extract_text(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'media.docx'
   with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_STORED) as z:
    z.writestr('word/document.xml','<w:document xmlns:w="urn:qa"><w:body><w:p><w:r><w:t>Public synthetic document text.</w:t></w:r></w:p></w:body></w:document>')
    with z.open('word/media/unused.bin','w') as image:
     for _ in range(34):image.write(b'x'*1024**2)
   self.assertGreater(path.stat().st_size,32*1024**2)
   self.assertIn('synthetic',next(x.extract_file(path,'media.docx'))['text'])
 def test_docx_entities_remain_forbidden(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'bad.docx'
   with zipfile.ZipFile(path,'w') as z:z.writestr('word/document.xml','<!DOCTYPE x [<!ENTITY attack "x">]><x/>')
   with self.assertRaises(ValueError):list(x.extract_file(path,'bad.docx'))
 def test_pdf_can_include_more_than_one_hundred_text_pages(self):
  from pypdf import PdfWriter
  from pypdf.generic import DecodedStreamObject,NameObject,DictionaryObject
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'pages.pdf';writer=PdfWriter()
   font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
   for _ in range(121):
    page=writer.add_blank_page(width=300,height=300);stream=DecodedStreamObject();stream.set_data(b'BT /F1 10 Tf 20 250 Td (Public synthetic document text with enough characters.) Tj ET')
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})});page[NameObject('/Contents')]=writer._add_object(stream)
   writer.write(path)
   self.assertEqual(max(c['page'] for c in x.extract_file(path,'pages.pdf')),121)
