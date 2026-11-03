"""Compatibility and failure checks against the real authenticated application."""
import pathlib,json,subprocess,importlib.util,sys
root=pathlib.Path(__file__).resolve().parents[2];stage='--stage' in sys.argv
target=json.loads((root/'tmp/document-upload-stage.json').read_text())['core'] if stage else 'ai-server-moara-gateway-1'
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import sys,json,httpx,hashlib,base64,uuid
token=json.load(sys.stdin)['token'];checks={};ids=[]
with httpx.Client(base_url='http://localhost:8075/api/v1/platform',trust_env=False,timeout=180,headers={'Authorization':'Bearer '+token}) as c:
 try:
  data=b'public synthetic compatibility text\n'*(160000)
  r=c.post('/documents',json={'filename':'compatibility.txt','title':'UPLOAD_QA_'+uuid.uuid4().hex,'content_base64':base64.b64encode(data).decode()});checks['legacy_json_above_four_mib_accepted']=r.status_code==201 and len(data)>4*1024**2;r.raise_for_status();ids.append(r.json()['id'])
  d=c.get('/documents/'+ids[-1]+'/download');checks['legacy_document_download_preserved']=d.status_code==200 and d.content==data
  raw=b'public synthetic raw upload\n'*400000
  r=c.post('/documents/upload',params={'filename':'streamed.txt','title':'UPLOAD_QA_'+uuid.uuid4().hex},content=raw);checks['raw_upload_above_eight_mib_accepted']=r.status_code==201 and len(raw)>8*1024**2;r.raise_for_status();ids.append(r.json()['id'])
  checks['server_sha256_matches']=r.json()['sha256']==hashlib.sha256(raw).hexdigest()
  d=c.get('/documents/'+ids[-1]+'/download');checks['segmented_download_bytes_match']=d.status_code==200 and d.content==raw
  for name,data,key in [('empty.txt',b'','empty_document'),('invalid.txt',b'\xff','utf8_document_required'),('invalid.pdf',b'garbage','invalid_pdf'),('../outside.txt',b'hello','invalid_filename')]:
   r=c.post('/documents/upload',params={'filename':name,'title':'UPLOAD_QA_REJECT_'+uuid.uuid4().hex},content=data)
   checks[key+'_rejected']=r.status_code==422 and r.json()['detail']==key
  r=httpx.post('http://localhost:8075/api/v1/platform/documents/upload',params={'filename':'x.txt','title':'x'},content=b'x',trust_env=False)
  checks['upload_requires_authentication']=r.status_code==401
 finally:
  for identifier in ids:
   row=c.get('/resources/'+identifier).json();r=c.post('/resources/'+identifier+'/archive',json={'version':row['version']});r.raise_for_status()
  checks['synthetic_documents_archived']=True
print(json.dumps({'checks':checks}))
'''
r=subprocess.run(['docker','exec','-i',target,'python','-c',code],input=json.dumps({'token':m.admin_session()}),text=True,capture_output=True,timeout=600)
if r.returncode:raise RuntimeError(r.stderr[-1600:])
report=json.loads(r.stdout);report['image']=subprocess.check_output(['docker','inspect',target,'--format','{{.Image}}'],text=True).strip()
(root/('docs/runtime/document-upload-live-stage.json' if stage else 'docs/runtime/document-upload-live-public.json')).write_text(json.dumps(report,indent=2))
print(json.dumps(report));assert all(report['checks'].values())
