import subprocess,json,importlib.util,tempfile,ssl,urllib.request
from pathlib import Path
ROOT=Path('/home/nutec/ai-server');BASE='https://moara.am.trf1.gov.br'
spec=importlib.util.spec_from_file_location('m',ROOT/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
token=m.admin_session();ctx=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/moara-domain-root-ca.crt'))
def api(path,method='GET'):
 req=urllib.request.Request(BASE+path,method=method,headers={'Authorization':'Bearer '+token})
 with urllib.request.urlopen(req,context=ctx,timeout=30) as r:return json.load(r)
try:
 cfg=api('/api/v1/retrieval/config');print({k:v for k,v in cfg.items() if 'FILE_MAX' in k or 'file_max' in k})
 with tempfile.NamedTemporaryFile(prefix='moara-upload-limit-') as tmp:
  tmp.write(b'x'*11868084);tmp.flush()
  config='header = "Authorization: Bearer '+token+'"\n'
  result=subprocess.run(['curl','--silent','--show-error','--config','-','--cacert',str(ROOT/'docs/runtime/moara-domain-root-ca.crt'),'-F','file=@'+tmp.name+';filename=moara-limit-test-ficticio.txt',BASE+'/api/v1/files/?process=false','-w','\n%{http_code}'],input=config.encode(),capture_output=True,timeout=60)
  body,_,code=result.stdout.rpartition(b'\n')
  print({'http_status':code.decode(),'response_bytes':len(body),'curl_exit':result.returncode})
  if code==b'200':
   f=json.loads(body);assert f['filename']=='moara-limit-test-ficticio.txt'
   api('/api/v1/files/'+f['id'],'DELETE');print('Unexpectedly accepted synthetic file removed.')
finally:api('/api/v1/auths/signout','POST')
