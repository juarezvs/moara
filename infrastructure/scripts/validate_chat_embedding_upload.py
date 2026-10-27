import importlib.util,json,ssl,urllib.request,time,uuid,subprocess,collections
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
token=module.admin_session();tls=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/moara-domain-root-ca.crt'))
BASE='https://moara.am.trf1.gov.br';filename='moara-validacao-embedding-'+uuid.uuid4().hex[:8]+'.txt'
size=1363149;line=b'Dado ficticio para validar upload em lotes. O prazo do procedimento Alfa e cinco dias uteis. '
content=(line*((size//len(line))+1))[:size]
boundary='MoaraTest'+uuid.uuid4().hex
body=('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="'+filename+'"\r\nContent-Type: text/plain\r\n\r\n').encode()+content+('\r\n--'+boundary+'--\r\n').encode()
def call(path,data=None,method=None,headers=None):
 req=urllib.request.Request(BASE+path,data=data,method=method,headers={'Authorization':'Bearer '+token,**(headers or {})})
 with urllib.request.urlopen(req,context=tls,timeout=180) as response:return json.load(response)
started=datetime.now(timezone.utc).isoformat();start=time.monotonic();identifier=None
report={'synthetic_only':True,'bytes':size,'upload_path':'/api/v1/files/','started_at':started}
dest=ROOT/'docs/runtime/embedding-upload-validation-20261027.json'
def save():dest.write_text(json.dumps(report,indent=2))
try:
 result=call('/api/v1/files/?process=true&process_in_background=true',body,headers={'Content-Type':'multipart/form-data; boundary='+boundary})
 identifier=result['id'];report['file_id']=identifier;report['upload_accepted']=True;save()
 deadline=time.monotonic()+1500
 while time.monotonic()<deadline:
  state=call('/api/v1/files/'+identifier+'/process/status');status=state['status']
  progress=state.get('progress') or {}
  if progress:report.setdefault('progress_samples',[]).append(progress)
  report['processing_status']=status;report['elapsed_seconds']=round(time.monotonic()-start,1);save()
  if status in ('completed','failed'):break
  time.sleep(5)
 if report.get('processing_status')!='completed':raise RuntimeError('synthetic_upload_not_completed')
 # Verify retrieval against only the newly uploaded synthetic file.
 query={'collection_name':'file-'+identifier,'query':'Qual o prazo do procedimento Alfa?','k':1,'hybrid':False}
 result=call('/api/v1/retrieval/query/doc',json.dumps(query).encode(),headers={'Content-Type':'application/json'})
 docs=result.get('documents') or []
 report['retrieved_chunks']=sum(len(x) for x in docs if isinstance(x,list))
 assert report['retrieved_chunks']>0
 report['passed']=True
finally:
 if identifier:
  item=call('/api/v1/files/'+identifier)
  if item['filename']!=filename:raise RuntimeError('synthetic_cleanup_identity_mismatch')
  call('/api/v1/files/'+identifier,method='DELETE');report['synthetic_file_removed']=True
 report['elapsed_seconds']=round(time.monotonic()-start,1)
 logs=subprocess.check_output(['docker','logs','--since',started,'ai-server-gateway-1'],stderr=subprocess.STDOUT).decode(errors='replace')
 counts=collections.Counter()
 for line in logs.splitlines():
  try:r=json.loads(line)
  except ValueError:continue
  if r.get('event')=='request' and r.get('route')=='/v1/embeddings' and r.get('client')=='webui':counts[str(r.get('status'))]+=1
 report['webui_embedding_statuses_during_validation']=dict(counts);save();print(json.dumps(report))
