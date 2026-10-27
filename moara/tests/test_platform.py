import base64,io,json,unittest,zipfile
from fastapi import HTTPException
from moara.gateway.platform_contracts import validate_body,validate_files,DatasetQuery
from moara.gateway.platform_documents import decode_upload,extract,render_template,aggregate,export_csv,docx_export
from moara.gateway.platform_store import digest
class PlatformTests(unittest.TestCase):
 def test_paths(self):
  for path in ('../secret','/etc/passwd','a/../../b','.env','a/.ssh/id','a\\b','C:/a','CON','a//b','x.'):
   with self.subTest(path=path),self.assertRaises(HTTPException):validate_files({path:'x'})
  self.assertEqual(validate_files({'src/main.py':'print(1)'}),{'src/main.py':'print(1)'})
 def test_resource_contract(self):
  for kind,body in [('assistant',{'tools':['shell']}),('assistant',{'tools':{}}),('assistant',{'tools':[{}]}),('workflow',{'steps':[{'type':'http.request'}]}),('workflow',{'steps':[{'type':'notification.test'}],'schedule':None}),('case',{'events':[{'bad':1}]})]:
   with self.subTest(kind=kind),self.assertRaises(HTTPException):validate_body(kind,body)
 def test_size(self):
  with self.assertRaises(HTTPException):validate_files({'a.py':'a'*200001})
 def test_upload(self):
  raw,media=decode_upload('ok.txt',base64.b64encode('Olá'.encode()).decode())
  self.assertEqual(raw.decode(),'Olá');self.assertEqual(media,'text/plain')
  for filename,data in [('a.exe','YQ=='),('a.pdf','YQ=='),('../a.txt','YQ=='),('a.txt','???')]:
   with self.assertRaises(HTTPException):decode_upload(filename,data)
 def test_docx_zip_bomb_limits(self):
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('word/document.xml',b'a'*(33*1024**2))
  with self.assertRaises(HTTPException):decode_upload('x.docx',base64.b64encode(out.getvalue()).decode())
 def test_template(self):
  self.assertEqual(render_template('Olá {{nome}}',['nome'],{'nome':'Ana'}),'Olá Ana')
  self.assertEqual(render_template('{{nome}}',['nome'],{'nome':'{{outro}}'}),'{{outro}}')
  with self.assertRaises(HTTPException):render_template('{{segredo}}',[],{})
  with self.assertRaises(HTTPException):render_template('{{nome}}',['nome'],{})
 def test_docx_round_trip(self):
  raw=docx_export('Olá, teste fictício.')
  self.assertIn('Olá, teste fictício.',extract(raw,'x.docx')[0]['text'])
  self.assertIn('RASCUNHO',extract(raw,'x.docx')[0]['text'])
 def test_chunks(self):
  chunks=extract(('Texto ' * 500).encode(),'a.txt')
  self.assertGreater(len(chunks),1);self.assertTrue(all(len(c['text'].encode())<=4400 for c in chunks))
 def test_analytics(self):
  spec=DatasetQuery(document_id='00000000-0000-0000-0000-000000000001',group_by='area',operation='average',value_column='dias')
  result=aggregate(b'area,dias\nA,2\nA,4\nB,8\n',spec)
  self.assertEqual(result['rows'][0],{'group':'A','value':'3','count':2})
  self.assertEqual(result['matched_rows'],3)
  spec.filters={'area':'B'};self.assertEqual(aggregate(b'area,dias\nA,2\nB,8\n',spec)['matched_rows'],1)
 def test_analytics_reject_nonfinite(self):
  spec=DatasetQuery(document_id='00000000-0000-0000-0000-000000000001',group_by='area',operation='sum',value_column='n')
  with self.assertRaises(HTTPException):aggregate(b'area,n\nA,NaN',spec)
 def test_csv_formula(self):
  self.assertIn("'=cmd",export_csv({'rows':[{'group':'=cmd','value':'2','count':2}]}))
 def test_canonical_digest(self):self.assertEqual(digest({'b':1,'a':2}),digest({'a':2,'b':1}))
if __name__=='__main__':unittest.main()

class InternalInferenceTests(unittest.IsolatedAsyncioTestCase):
 async def test_job_inference_disables_connector_interpretation(self):
  from unittest.mock import patch
  from types import SimpleNamespace
  from moara.gateway.platform_runs import model_text
  async def completion(body,request,actor):
   self.assertTrue(request.scope.get('moara_disable_data_tools'))
   return {'choices':[{'message':{'content':'synthetic'}}]}
  with patch('moara.gateway.platform_runs.completion',completion):
   result=await model_text(SimpleNamespace(),SimpleNamespace(require=lambda p:None),'synthetic')
  self.assertEqual(result,'synthetic')

class ResultSerializationTests(unittest.TestCase):
 def test_database_types_roundtrip_encrypted(self):
  from types import SimpleNamespace
  from cryptography.fernet import Fernet
  from decimal import Decimal
  from uuid import UUID
  from moara.gateway.platform_store import seal,unseal
  crypto=Fernet(Fernet.generate_key());app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(fernet=lambda:crypto)))
  value={'id':UUID('00000000-0000-0000-0000-000000000001'),'score':Decimal('0.25')}
  decoded=unseal(app,seal(app,value))
  self.assertEqual(decoded['id'],str(value['id']));self.assertEqual(decoded['score'],0.25)

class ExportTests(unittest.TestCase):
 def test_docx_split_runs_tables_and_styles(self):
  from docx import Document
  from moara.gateway.platform_exports import fill_docx
  doc=Document();p=doc.add_paragraph('Olá ');p.add_run('{{no').bold=True;p.add_run('me}}!')
  doc.add_table(rows=1,cols=1).cell(0,0).text='Responsável: {{nome}}'
  doc.sections[0].header.paragraphs[0].text='Equipe {{nome}}'
  out=io.BytesIO();doc.save(out)
  raw,text=fill_docx(out.getvalue(),['nome'],{'nome':'Ana'})
  restored=Document(io.BytesIO(raw))
  self.assertEqual(restored.paragraphs[0].text,'Olá Ana!')
  self.assertTrue(restored.paragraphs[0].runs[1].bold)
  self.assertEqual(restored.tables[0].cell(0,0).text,'Responsável: Ana')
  self.assertIn('Equipe Ana',restored.sections[0].header.paragraphs[0].text)
  self.assertTrue(any('RASCUNHO' in p.text for p in restored.sections[0].header.paragraphs))
 def test_pdf_text_unicode_and_pagination(self):
  from moara.gateway.platform_exports import pdf_text
  from pypdf import PdfReader
  reader=PdfReader(io.BytesIO(pdf_text('\n'.join(['Revisão fictícia — ação número 42.']*90))))
  self.assertGreater(len(reader.pages),1)
  self.assertIn('Revisão fictícia',reader.pages[0].extract_text())
  self.assertIn('RASCUNHO',reader.pages[0].extract_text())
 def test_pdf_unsupported_character_is_explicit(self):
  from moara.gateway.platform_exports import pdf_text
  with self.assertRaises(ValueError):pdf_text('Emoji não substituído silenciosamente: 😀')
 def test_git_history_roundtrip(self):
  import tempfile,subprocess
  from pathlib import Path
  from moara.gateway.platform_exports import git_bundle
  raw=git_bundle([{'version':1,'files':{'src/old.py':'print(1)'}},{'version':2,'files':{'main.py':'print(42)'}}])
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'project.bundle').write_bytes(raw)
   subprocess.run(['git','clone',str(root/'project.bundle'),str(root/'checkout')],check=True,capture_output=True)
   self.assertEqual((root/'checkout/main.py').read_text(),'print(42)')
   self.assertFalse((root/'checkout/src/old.py').exists())
   count=subprocess.check_output(['git','-C',str(root/'checkout'),'rev-list','--count','HEAD'],text=True).strip()
   self.assertEqual(count,'2')
 def test_file_directory_collision_rejected(self):
  with self.assertRaises(HTTPException):validate_files({'src':'x','src/a.py':'y'})
 def test_unknown_agent_rejected_at_contract_boundary(self):
  from moara.gateway.platform_runs import AGENT_PROMPTS
  self.assertEqual(len(AGENT_PROMPTS),9)
  self.assertNotIn('shell',AGENT_PROMPTS)
