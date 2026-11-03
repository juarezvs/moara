import importlib.util,json,ssl,socket,subprocess,base64,hashlib,re,urllib.request
from pathlib import Path
ROOT=Path('/home/nutec/ai-server');WORK=Path('/home/nutec/moara-auto-documents-20261027')
ctx=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/moara-domain-root-ca.crt'))
with socket.create_connection(('moara.am.trf1.gov.br',443),timeout=20) as sock:
 with ctx.wrap_socket(sock,server_hostname='moara.am.trf1.gov.br') as tls:cert=ssl.DER_cert_to_PEM_cert(tls.getpeercert(binary_form=True))
pub=subprocess.check_output(['openssl','x509','-pubkey','-noout'],input=cert.encode());der=subprocess.check_output(['openssl','pkey','-pubin','-outform','DER'],input=pub)
spki=base64.b64encode(hashlib.sha256(der).digest()).decode()
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
token=module.admin_session()
name='moara-auto-documents-browser-20261027'
subprocess.run(['docker','run','-d','--name',name,'--label','moara.test=chat-feedback','--memory','2g','--cpus','2','--pids-limit','256','--add-host','moara.am.trf1.gov.br:172.19.5.250','-v',str(WORK)+':/tests:ro','--entrypoint','sleep','ia-studio-renderer:1.0.0','infinity'],check=True,capture_output=True)
try:
 result=subprocess.run(['docker','exec','-i',name,'python','/tests/browser_test.py'],input=json.dumps({'token':token,'spki':spki}).encode(),capture_output=True,timeout=1500)
 clean=lambda b:b.decode().replace(token,'[REDACTED_TEMPORARY_TEST_SESSION]')
 print(clean(result.stdout));print(clean(result.stderr)[-2000:])
 for name_image in ['automatic-document-0.png','automatic-document-1.png','automatic-document-2.png']:
  subprocess.run(['docker','cp',name+':/tmp/'+name_image,str(WORK/name_image)],capture_output=True)
finally:
 subprocess.run(['docker','rm','-f',name],capture_output=True)
 req=urllib.request.Request('https://moara.am.trf1.gov.br/api/v1/auths/signout',data=b'{}',headers={'Authorization':'Bearer '+token})
 with urllib.request.urlopen(req,context=ctx,timeout=30) as response:assert response.status==200
raise SystemExit(result.returncode)
