"""File-backed, page-at-a-time extraction for the document ingestion worker."""
import argparse,json,os,subprocess,tempfile,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

def text_chunks(parts):
 buffer=''
 for part in parts:
  buffer+=part.replace('\x00','')
  while len(buffer)>=1100:
   text=buffer[:1100].strip();buffer=buffer[900:]
   if text:yield text
 if buffer.strip():yield buffer.strip()

def docx_parts(path):
 with zipfile.ZipFile(path) as z:
  names=z.namelist()
  if len(names)!=len(set(names)) or 'word/document.xml' not in names:raise ValueError('invalid_docx')
  if any('vbaproject' in n.casefold() or n.startswith('/') or '..' in n.split('/') for n in names):raise ValueError('unsupported_docx_content')
  # Never resolve entities, fetch external relationships or load embedded media.
  with z.open('word/document.xml') as source:
   tail=b''
   while part:=source.read(65536):
    check=(tail+part).lower()
    if b'<!doctype' in check or b'<!entity' in check:raise ValueError('unsupported_xml_declaration')
    tail=check[-32:]
  with z.open('word/document.xml') as source:
   stack=[]
   for event,element in ET.iterparse(source,events=('start','end')):
    if event=='start':stack.append(element);continue
    if element.tag.rsplit('}',1)[-1]=='p':
     yield ''.join(element.itertext())+'\n'
     element.clear()
     if len(stack)>1:stack[-2].remove(element)
    stack.pop()

def extract_file(path,filename):
 suffix=Path(filename).suffix.lower()
 if suffix=='.pdf':
  from pypdf import PdfReader
  with open(path,'rb') as source:
   reader=PdfReader(source)
   if reader.is_encrypted:raise ValueError('encrypted_pdf')
   for number,page in enumerate(reader.pages,1):
    text=page.extract_text() or '';ocr=False
    if len(text.strip())<20:
     with tempfile.TemporaryDirectory(prefix='ocr-',dir=Path(path).parent) as folder:
      target=Path(folder)/'page'
      subprocess.run(['pdftoppm','-f',str(number),'-l',str(number),'-r','120','-scale-to','2400','-singlefile','-png',str(path),str(target)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
      result=subprocess.run(['tesseract',str(target)+'.png','stdout','-l','por+eng','--psm','3'],capture_output=True,check=True,timeout=30,env={**os.environ,'OMP_THREAD_LIMIT':'1'})
      text=result.stdout.decode('utf8');ocr=True
    for chunk in text_chunks([text]):yield {'page':number,'text':chunk,'ocr':ocr}
 elif suffix=='.docx':
  for text in text_chunks(docx_parts(path)):yield {'page':None,'text':text,'ocr':False}
 elif suffix=='.xlsx':
  from .xlsx_documents import extract
  for page in extract(path):
   for text in text_chunks([page['text']]):yield {'page':page.get('page'),'text':text,'ocr':False}
 else:
  with open(path,encoding='utf-8-sig') as source:
   for text in text_chunks(iter(lambda:source.read(65536),'')):yield {'page':None,'text':text,'ocr':False}

def main():
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(1024*1024**2,1024*1024**2))
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--filename',required=True);args=p.parse_args()
 count=0
 with open(args.output,'w',encoding='utf8') as out:
  for chunk in extract_file(args.input,args.filename):out.write(json.dumps(chunk,ensure_ascii=False)+'\n');count+=1
 if not count:raise ValueError('empty_document')
if __name__=='__main__':main()
