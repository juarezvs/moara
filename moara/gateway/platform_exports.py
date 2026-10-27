"""Bounded exports: formatted DOCX, text-review PDF and portable local Git history."""
import base64,io,json,os,re,subprocess,sys,tempfile,textwrap
from pathlib import Path
from fastapi import HTTPException
from .platform_contracts import validate_files
from .platform_documents import render_template
TOKEN=re.compile(r'{{\s*([A-Za-z][A-Za-z0-9_]*)\s*}}')

def paragraphs(container):
 for paragraph in container.paragraphs:yield paragraph
 for table in container.tables:
  for row in table.rows:
   for cell in row.cells:yield from paragraphs(cell)

def replace_paragraph(paragraph,fields):
 text=paragraph.text
 for match in reversed(list(TOKEN.finditer(text))):
  positions=[];offset=0
  for run in paragraph.runs:
   positions.append((run,offset,offset+len(run.text)));offset+=len(run.text)
  selected=[(run,start,end) for run,start,end in positions if end>match.start() and start<match.end()]
  if not selected:continue
  first,start,_=selected[0];last,last_start,_=selected[-1]
  prefix=first.text[:match.start()-start];suffix=last.text[match.end()-last_start:]
  if first is last:first.text=prefix+fields[match[1]]+suffix
  else:
   first.text=prefix+fields[match[1]]
   for run,_,_ in selected[1:-1]:run.text=''
   last.text=suffix

def fill_docx(raw,variables,fields):
 from docx import Document
 doc=Document(io.BytesIO(raw));items=list(paragraphs(doc))
 for section in doc.sections:
  items+=list(paragraphs(section.header));items+=list(paragraphs(section.footer))
 text='\n'.join(p.text for p in items)
 render_template(text,variables,fields)
 for paragraph in items:replace_paragraph(paragraph,fields)
 for section in doc.sections:
  if not any('RASCUNHO' in p.text for p in section.header.paragraphs):
   section.header.add_paragraph('RASCUNHO — revisão humana obrigatória')
 out=io.BytesIO();doc.save(out)
 return out.getvalue(),'\n'.join(p.text for p in paragraphs(doc))

def pdf_text(text):
 """Portable paginated WinAnsi text proof; never claims DOCX layout fidelity."""
 from pypdf import PdfWriter
 from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
 if len(text)>150000:raise ValueError('export_text_limit')
 try:text.encode('cp1252')
 except UnicodeEncodeError:raise ValueError('pdf_charset_use_docx') from None
 writer=PdfWriter()
 font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),
  NameObject('/BaseFont'):NameObject('/Courier'),NameObject('/Encoding'):NameObject('/WinAnsiEncoding')})
 lines=[]
 for line in text.splitlines():lines.extend(textwrap.wrap(line,width=80,replace_whitespace=False,drop_whitespace=False) or [''])
 def literal(value):return value.encode('cp1252').replace(b'\\',b'\\\\').replace(b'(',b'\\(').replace(b')',b'\\)')
 for start in range(0,max(1,len(lines)),48):
  page=writer.add_blank_page(width=595,height=842)
  page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
  content=b'BT /F1 10 Tf 14 TL 50 790 Td ('+literal('RASCUNHO - revisão humana obrigatória')+b') Tj T* T*\n'
  for line in lines[start:start+48]:content+=b'('+literal(line)+b') Tj T*\n'
  content+=b'ET\nBT /F1 9 Tf 50 35 Td ('+literal('Página '+str(start//48+1))+b') Tj ET'
  stream=DecodedStreamObject();stream.set_data(content);page[NameObject('/Contents')]=writer._add_object(stream)
 writer.add_metadata({'/Title':'Moara — rascunho para revisão','/Producer':'Moara local text proof'})
 out=io.BytesIO();writer.write(out);return out.getvalue()

def git_bundle(versions):
 if not isinstance(versions,list) or not 1<=len(versions)<=100:raise ValueError('version_limit')
 with tempfile.TemporaryDirectory(prefix='moara-git-') as folder:
  root=Path(folder);repo=root/'project';repo.mkdir()
  env={**os.environ,'HOME':str(root),'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':os.devnull,
   'GIT_TERMINAL_PROMPT':'0','GIT_CONFIG_COUNT':'0','GIT_ALLOW_PROTOCOL':''}
  for key in list(env):
   if key.startswith('GIT_') and key not in {'GIT_CONFIG_NOSYSTEM','GIT_CONFIG_GLOBAL','GIT_TERMINAL_PROMPT','GIT_CONFIG_COUNT','GIT_ALLOW_PROTOCOL'}:env.pop(key)
  def git(*args):
   subprocess.run(['git','-c','core.hooksPath='+os.devnull,*args],cwd=repo,env=env,check=True,capture_output=True,timeout=15)
  git('init','--initial-branch=main');git('config','user.name','Moara');git('config','user.email','moara@localhost')
  previous=set()
  for version in versions:
   files=validate_files(version['files'])
   for name in previous-set(files):(repo/name).unlink(missing_ok=True)
   for name in previous:
    parent=(repo/name).parent
    while parent!=repo:
     try:parent.rmdir()
     except OSError:break
     parent=parent.parent
   for name,content in files.items():
    path=repo/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding='utf-8')
   git('add','--all');git('commit','--allow-empty','-m','Moara version '+str(int(version['version'])))
   previous=set(files)
  bundle=root/'project.bundle';git('bundle','create',str(bundle),'main','HEAD')
  if bundle.stat().st_size>32*1024**2:raise ValueError('bundle_size_limit')
  return bundle.read_bytes()

def isolated(action,payload):
 try:p=subprocess.run([sys.executable,'-m','moara.gateway.platform_exports'],input=json.dumps({'action':action,**payload}).encode(),capture_output=True,timeout=45)
 except subprocess.TimeoutExpired:raise HTTPException(422,'export_timeout') from None
 if p.returncode:raise HTTPException(422,'export_failed_check_template_or_charset')
 return json.loads(p.stdout)

if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
 resource.setrlimit(resource.RLIMIT_CPU,(30,30))
 resource.setrlimit(resource.RLIMIT_FSIZE,(64*1024**2,64*1024**2))
 try:
  payload=json.loads(sys.stdin.buffer.read(20000000));action=payload['action']
  if action=='git':result={'bundle_base64':base64.b64encode(git_bundle(payload['versions'])).decode()}
  elif action=='docx':
   raw,text=fill_docx(base64.b64decode(payload['source'],validate=True),payload['variables'],payload['fields'])
   result={'docx_base64':base64.b64encode(raw).decode(),'text':text}
  elif action=='pdf':result={'pdf_base64':base64.b64encode(pdf_text(payload['text'])).decode()}
  else:raise ValueError()
  sys.stdout.write(json.dumps(result))
 except Exception:sys.exit(2)
