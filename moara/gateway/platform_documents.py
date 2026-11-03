"""Bounded document extraction, deterministic templates and reproducible analytics."""
import tempfile
import base64,csv,hashlib,io,json,math,re,subprocess,sys,zipfile
from decimal import Decimal,InvalidOperation
from pathlib import PurePosixPath
from fastapi import HTTPException

MEDIA={'.txt':'text/plain','.md':'text/markdown','.csv':'text/csv','.pdf':'application/pdf',
 '.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
 '.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
def decode_upload(filename,encoded):
 if '/' in filename or '\\' in filename or filename.startswith('.'):raise HTTPException(422,'invalid_filename')
 suffix=PurePosixPath(filename).suffix.lower()
 if suffix not in MEDIA:raise HTTPException(422,'unsupported_document_type')
 try:raw=base64.b64decode(encoded,validate=True)
 except ValueError:raise HTTPException(422,'invalid_base64') from None
 if not raw:raise HTTPException(422,'empty_document')
 if suffix=='.pdf' and not raw.startswith(b'%PDF-'):raise HTTPException(422,'invalid_pdf')
 if suffix=='.xlsx':
  try:
   from .xlsx_documents import archive
   with archive(raw):pass
  except (ValueError,zipfile.BadZipFile,KeyError):raise HTTPException(422,'invalid_xlsx') from None
 if suffix=='.docx':
  try:
   with zipfile.ZipFile(io.BytesIO(raw)) as z:
    if len(z.infolist())>3000 or sum(i.file_size for i in z.infolist())>32*1024**2:raise ValueError()
    if 'word/document.xml' not in z.namelist() or any('vbaProject' in i.filename for i in z.infolist()):raise ValueError()
  except (ValueError,zipfile.BadZipFile):raise HTTPException(422,'invalid_docx') from None
 if suffix in ('.txt','.md','.csv'):
  try:raw.decode('utf-8-sig')
  except UnicodeDecodeError:raise HTTPException(422,'utf8_document_required') from None
 return raw,MEDIA[suffix]

def extract(raw,filename):
 suffix=PurePosixPath(filename).suffix.lower()
 if suffix=='.pdf':
  from pypdf import PdfReader
  reader=PdfReader(io.BytesIO(raw))
  if reader.is_encrypted or len(reader.pages)>100:raise ValueError('pdf_limit_or_encrypted')
  pages=[{'page':i+1,'text':p.extract_text() or ''} for i,p in enumerate(reader.pages)]
  scanned=[p for p in pages if len(p['text'].strip())<20]
  if len(scanned)>20:raise ValueError('ocr_page_limit')
  if scanned:
   from pathlib import Path
   with tempfile.TemporaryDirectory(prefix='moara-ocr-') as folder:
    source=Path(folder)/'input.pdf';source.write_bytes(raw)
    for page in scanned:
     target=Path(folder)/'page'
     subprocess.run(['pdftoppm','-f',str(page['page']),'-l',str(page['page']),'-r','120','-scale-to','2400','-singlefile','-png',str(source),str(target)],capture_output=True,check=True,timeout=15)
     result=subprocess.run(['tesseract',str(target)+'.png','stdout','-l','por+eng','--psm','3'],capture_output=True,check=True,timeout=20,env={**__import__('os').environ,'OMP_THREAD_LIMIT':'1'})
     page['text']=result.stdout.decode('utf-8');page['ocr']=True
     Path(str(target)+'.png').unlink()
 elif suffix=='.xlsx':
  from .xlsx_documents import extract as extract_xlsx
  pages=extract_xlsx(raw)
 elif suffix=='.docx':
  from docx import Document
  doc=Document(io.BytesIO(raw));parts=[p.text for p in doc.paragraphs]
  parts += [' | '.join(c.text for c in r.cells) for t in doc.tables for r in t.rows]
  pages=[{'page':None,'text':'\n'.join(parts)}]
 else:pages=[{'page':None,'text':raw.decode('utf-8-sig')}]
 if sum(len(p['text']) for p in pages)>1000000:raise ValueError('extracted_text_limit')
 chunks=[]
 for page in pages:
  text=page['text'].replace('\x00','')
  # UTF-8 byte bound is below the local embeddings API's per-input limit.
  for start in range(0,len(text),900):
   part=text[start:start+1100].strip()
   if part:chunks.append({'page':page['page'],'text':part,'ocr':page.get('ocr',False)})
 if len(chunks)>1200:raise ValueError('chunk_limit')
 if not chunks:raise ValueError('empty_document')
 return chunks

def isolated_extract(raw,filename):
 payload=json.dumps({'filename':filename,'data':base64.b64encode(raw).decode()}).encode()
 try:
  p=subprocess.run([sys.executable,'-m','moara.gateway.platform_documents'],input=payload,capture_output=True,timeout=180)
 except subprocess.TimeoutExpired:raise HTTPException(422,'extraction_timeout') from None
 if p.returncode:raise HTTPException(422,'document_extraction_failed_or_ocr_required')
 return json.loads(p.stdout)

def render_template(text,variables,fields):
 if set(fields)!=set(variables):raise HTTPException(422,'template_fields_mismatch')
 if any(len(v)>20000 for v in fields.values()):raise HTTPException(413,'template_field_too_large')
 used=set(re.findall(r'{{\s*([A-Za-z][A-Za-z0-9_]*)\s*}}',text))
 if used-set(variables):raise HTTPException(422,'undeclared_template_variable')
 return re.sub(r'{{\s*([A-Za-z][A-Za-z0-9_]*)\s*}}',lambda m:fields[m[1]],text)

def aggregate(raw,spec):
 try:
  text=raw.decode('utf-8-sig');reader=csv.DictReader(io.StringIO(text))
  headers=reader.fieldnames or []
  required={spec.group_by,*spec.filters}
  if spec.operation!='count':
   if not spec.value_column:raise ValueError()
   required.add(spec.value_column)
  if len(headers)>100 or len(set(headers))!=len(headers) or not required<=set(headers):raise ValueError()
  buckets={};matched=0
  for number,row in enumerate(reader,1):
   if number>50000 or None in row:raise ValueError()
   if any(row[k]!=v for k,v in spec.filters.items()):continue
   key=row[spec.group_by]
   if key is None or len(key)>500:raise ValueError()
   item=buckets.setdefault(key,[Decimal(0),0])
   if len(buckets)>2000:raise ValueError()
   value=Decimal(1) if spec.operation=='count' else Decimal(row[spec.value_column])
   if not value.is_finite() or abs(value)>Decimal('1e18'):raise ValueError()
   item[0]+=value;item[1]+=1;matched+=1
  rows=[{'group':k,'value':str(v[0]/v[1] if spec.operation=='average' else v[0]),'count':v[1]} for k,v in sorted(buckets.items())]
 except (ValueError,InvalidOperation,UnicodeError,csv.Error,TypeError):raise HTTPException(422,'invalid_dataset_or_query') from None
 return {'rows':rows,'matched_rows':matched,'definition':spec.model_dump(mode='json'),
  'source_sha256':hashlib.sha256(raw).hexdigest(),'method':'deterministic_csv_v1'}

def export_csv(result):
 out=io.StringIO();w=csv.writer(out);w.writerow(['grupo','valor','registros'])
 def safe(s):return "'"+s if s.lstrip().startswith(('=','+','-','@','\t','\r')) else s
 for row in result['rows']:w.writerow([safe(row['group']),row['value'],row['count']])
 return out.getvalue()

def docx_export(text):
 from docx import Document
 doc=Document();doc.add_heading('RASCUNHO — revisão humana obrigatória',0)
 for line in text.splitlines():doc.add_paragraph(line)
 out=io.BytesIO();doc.save(out);return out.getvalue()

if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
 resource.setrlimit(resource.RLIMIT_CPU,(120,120))
 resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,16*1024**2))
 data=json.loads(sys.stdin.buffer.read(6000000))
 try:sys.stdout.write(json.dumps(extract(base64.b64decode(data['data'],validate=True),data['filename'])))
 except Exception:sys.exit(2)
