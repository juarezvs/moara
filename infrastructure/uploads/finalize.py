"""Record end-to-end verification and retire only this release's private candidates."""
import pathlib,json,subprocess,importlib.util,re
root=pathlib.Path(__file__).resolve().parents[2];checks={}
def output(args):return subprocess.check_output(args,text=True).strip()
image=output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'])
tests=json.loads((root/'tmp/document-upload-tests.json').read_text())
checks['backend_tests']=tests['passed'] and tests['tests']>=312 and tests['image']==image
front=(root/'tmp/document-upload-angular.log').read_text()
front=re.sub(r'\x1b\[[0-9;]*m','',front)
checks['frontend_build_and_13_tests']='Output location:' in front and '13 passed' in front
for filename,field in [('document-upload-ui-stage.json','tested_image_id'),('document-upload-ui-public.json','tested_image_id'),('document-upload-live-stage.json','image'),('document-upload-live-public.json','image')]:
 r=json.loads((root/'docs/runtime'/filename).read_text());checks[filename]=all(r['checks'].values()) and r[field]==image
release=json.loads((root/'docs/runtime/document-upload-release.json').read_text());checks.update(release['checks'])
checks['backup_verified']=json.loads((root/'docs/runtime/moara-preservation-latest.json').read_text())['verified'] is True
sql="""SELECT json_build_object('version',(SELECT version_num FROM moara.alembic_version),'bigint',EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='moara' AND table_name='document_blobs' AND column_name='size_bytes' AND data_type='bigint'),'encrypted_segments_exist',EXISTS(SELECT 1 FROM moara.document_segments WHERE content LIKE 'gAAAA%' AND ordinal>0),'unfinished_upload_resources', (SELECT count(*) FROM moara.resources WHERE title LIKE 'UPLOAD_QA_REJECT_%'));"""
r=subprocess.run(['docker','exec','-i','ai-server-postgres-1','psql','-X','-v','ON_ERROR_STOP=1','-U','postgres','-d','ai','-At'],input=sql,text=True,capture_output=True,check=True);db=json.loads(r.stdout)
checks['database_expansion_and_encryption']=db['version']=='0011_streamed_documents' and db['bigint'] and db['encrypted_segments_exist']
checks['rejected_uploads_rolled_back']=db['unfinished_upload_resources']==0
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code="""import sys,json,httpx
with httpx.Client(trust_env=False,timeout=20) as c:
 r=c.get('http://localhost:8075/api/v1/observability/inference',headers={'Authorization':'Bearer '+sys.stdin.read().strip()});r.raise_for_status();v=r.json()
 print(json.dumps({k:v.get(k) for k in ['available','principal_resident','embeddings_resident']}))
"""
r=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session(),text=True,capture_output=True,check=True);inference=json.loads(r.stdout)
checks['models_remain_resident']=inference['principal_resident'] is True and inference['embeddings_resident'] is True
hashcode="""import pathlib,json,hashlib
paths=['moara/gateway/auth.py','moara/gateway/admin_api.py','moara/gateway/rbac.py','moara/gateway/legal_drafting.py','moara/gateway/migrations/010_api_key_unlimited_rpm.sql'];root=pathlib.Path('/app');data={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}
for p in (root/'web').rglob('*'):
 if p.is_file() and str(p.relative_to(root/'web')).startswith(('brand/','fonts/','integrations/')):data[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps(data))
"""
before=json.loads(output(['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL','--entrypoint','python','moara-core:pre-document-upload-20261102','-c',hashcode]))
after=json.loads(output(['docker','exec','ai-server-moara-gateway-1','python','-c',hashcode]));checks['auth_rbac_legal_drafting_and_brand_preserved']=before==after
assert all(checks.values()),checks
names=output(['docker','ps','--format','{{.Names}}']).splitlines();owned=[n for n in names if re.fullmatch(r'moara-document-upload-(stage|tls)-[0-9a-f]{10}',n)]
if owned:subprocess.run(['docker','stop',*owned],check=True,capture_output=True)
report={'published':True,'image':image,'checks':checks,'backend_tests':tests['tests'],'frontend_tests':13,'inference':inference,'database':db,'retired_private_candidates':owned}
(root/'docs/runtime/document-upload-final.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
