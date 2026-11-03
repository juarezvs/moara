"""Record the exact frontend release and clean up only its private candidates."""
import pathlib,json,subprocess,importlib.util,re
root=pathlib.Path(__file__).resolve().parents[2];checks={}
release=json.loads((root/'docs/runtime/page-scroll-release.json').read_text())
image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
checks['published_tested_image']=release['published'] and image==release['image']
for environment in ['stage','public']:
 report=json.loads((root/f'docs/runtime/page-scroll-ui-{environment}.json').read_text())
 checks[environment+'_browser_checks']=report['tested_image_id']==image and bool(report['checks']) and all(report['checks'].values())
hashcode="""import pathlib,hashlib,json
r=pathlib.Path('/app/moara');print(json.dumps({str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in r.rglob('*') if p.is_file() and '__pycache__' not in str(p)}))
"""
before=json.loads(subprocess.check_output(['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL','--entrypoint','python','moara-core:pre-page-scroll-app-20261102','-c',hashcode],text=True))
after=json.loads(subprocess.check_output(['docker','exec','ai-server-moara-gateway-1','python','-c',hashcode],text=True))
checks['backend_and_identity_files_unchanged']=before==after
for service in ['ai-server-moara-gateway-1','ai-server-moara-legal-mcp-1']:
 checks[service+'_healthy']=subprocess.check_output(['docker','inspect',service,'--format','{{.State.Health.Status}}'],text=True).strip()=='healthy'
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code="""import sys,json,httpx
token=sys.stdin.read().strip()
with httpx.Client(trust_env=False,timeout=20) as c:
 r=c.get('http://localhost:8075/api/v1/observability/inference',headers={'Authorization':'Bearer '+token});r.raise_for_status();v=r.json()
 print(json.dumps({k:v.get(k) for k in ['available','principal_resident','embeddings_resident']}))
"""
r=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session(),capture_output=True,text=True,check=True)
inference=json.loads(r.stdout)
checks['gpu_models_resident']=inference['available'] and inference['principal_resident'] and inference['embeddings_resident']
assert all(checks.values()),checks
names=subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines()
owned=[n for n in names if re.fullmatch(r'moara-page-scroll-(stage|tls)-[0-9a-f]{10}',n)]
if owned:subprocess.run(['docker','stop',*owned],capture_output=True,check=True)
result={'published':True,'image':image,'checks':checks,'inference':inference,'frontend_only':True,'stopped_private_candidates':owned}
(root/'docs/runtime/page-scroll-final.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
