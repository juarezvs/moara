import pathlib,subprocess,json,importlib.util,re
root=pathlib.Path(__file__).resolve().parents[2];checks={}
image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
tests=json.loads((root/'tmp/chat-stream-tests.json').read_text())
checks['tested_image_published']=tests['passed'] and tests['tests']>=264 and tests['image']==image
checks['frontend_tests_passed']='10 passed' in re.sub(r'\x1b\[[0-9;]*m','',(root/'tmp/chat-stream-unit.log').read_text())
reports={}
for filename in ['chat-stream-ui-stage.json','chat-stream-ui-public.json','chat-stream-citations-stage.json','chat-stream-citations-public.json']:
 report=json.loads((root/'docs/runtime'/filename).read_text())
 checks[filename]=report['tested_image_id']==image and bool(report['checks']) and all(report['checks'].values())
 reports[filename]={'checks':len(report['checks']),'metrics':report.get('metrics',{})}
hashcode="""import pathlib,hashlib,json
r=pathlib.Path('/app/moara')
print(json.dumps({str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in r.rglob('*.py')}))
"""
def hashes(target,running=False):
 args=['docker','exec',target,'python','-c',hashcode] if running else ['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL','--entrypoint','python',target,'-c',hashcode]
 return json.loads(subprocess.check_output(args,text=True))
before=hashes('moara-core:pre-chat-stream-app-20261102');after=hashes('ai-server-moara-gateway-1',True)
changed={p for p in after if p not in before or before[p]!=after[p]}
checks['unrelated_backend_modules_preserved']=set(before)<=set(after) and changed=={'gateway/chat_api.py','gateway/chat_delivery.py'}
checks['legal_mcp_preserved']=subprocess.check_output(['docker','inspect','ai-server-moara-legal-mcp-1','--format','{{.Image}}'],text=True).strip()=='sha256:37ca22156212c9ddc0ff21a69b46302c3fde2d9018583f21144d3082542f6588'
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code="""import sys,httpx,json
token=sys.stdin.read().strip()
with httpx.Client(trust_env=False,timeout=20) as c:
 r=c.get('http://localhost:8075/api/v1/observability/inference',headers={'Authorization':'Bearer '+token});r.raise_for_status();v=r.json()
 print(json.dumps({k:v.get(k) for k in ['available','principal_resident','embeddings_resident']}))
"""
r=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session(),capture_output=True,text=True,check=True)
inference=json.loads(r.stdout)
checks['principal_resident']=inference['principal_resident'] is True
checks['embeddings_resident']=inference['embeddings_resident'] is True
assert all(checks.values()),checks
names=subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines()
owned=[n for n in names if re.fullmatch(r'moara-chat-stream-(stage|tls)-[0-9a-f]{10}',n)]
if owned:subprocess.run(['docker','stop',*owned],check=True,stdout=subprocess.DEVNULL)
result={'published':True,'tested_image_id':image,'unit_tests':tests['tests'],'frontend_tests':10,'checks':checks,'browser_reports':reports,'inference':inference,'changed_backend_modules':sorted(changed),'database_migrations':False,'stopped_private_candidates':owned}
(root/'docs/runtime/chat-stream-final.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
