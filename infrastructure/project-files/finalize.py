import pathlib,subprocess,json,importlib.util,re
root=pathlib.Path(__file__).resolve().parents[2];checks={}
image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
tests=json.loads((root/'tmp/project-files-tests.json').read_text())
checks['tested_image_is_published']=tests['passed'] and tests['tests']>=261 and tests['image']==image
for name in ['project-files-ui-qualified-stage.json','project-files-ui-public.json']:
 report=json.loads((root/'docs/runtime'/name).read_text())
 checks[name]=report['tested_image_id']==image and bool(report['checks']) and all(report['checks'].values())
local=json.loads((root/'docs/runtime/project-files-local.json').read_text())
checks['local_project_tools']=bool(local['checks']) and all(local['checks'].values())
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code="""import sys,httpx,json
token=sys.stdin.read().strip()
with httpx.Client(trust_env=False,timeout=20) as c:
 r=c.get('http://localhost:8075/api/v1/observability/inference',headers={'Authorization':'Bearer '+token});r.raise_for_status();v=r.json()
 print(json.dumps({'available':v.get('available'),'principal_resident':v.get('principal_resident'),'embeddings_resident':v.get('embeddings_resident')}))
"""
r=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session(),text=True,capture_output=True,check=True)
inference=json.loads(r.stdout)
checks['principal_remains_resident']=inference['principal_resident'] is True
checks['embeddings_remain_resident']=inference['embeddings_resident'] is True
checks['metadata_timer_active']=subprocess.check_output(['systemctl','--user','is-active','moara-legal-metadata.timer'],text=True).strip()=='active'
hashcode="""import pathlib,hashlib,json
r=pathlib.Path('/app/moara')
print(json.dumps({str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in r.rglob('*.py')}))
"""
def hashes(name,running=False):
 args=['docker','exec',name,'python','-c',hashcode] if running else ['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL','--entrypoint','python',name,'-c',hashcode]
 return json.loads(subprocess.check_output(args,text=True))
old=hashes('moara-core:pre-project-files-app-20261102');new=hashes('ai-server-moara-gateway-1',True)
changed={p for p in new if p not in old or new[p]!=old[p]}
checks['unrelated_backend_modules_preserved']=set(old)<=set(new) and changed=={'gateway/project_tree.py','gateway/project_agent.py','gateway/platform_development.py','gateway/platform_contracts.py','gateway/developer_api.py'}
mcp=subprocess.check_output(['docker','inspect','ai-server-moara-legal-mcp-1','--format','{{.Image}}'],text=True).strip()
checks['legal_mcp_image_preserved']=mcp=='sha256:37ca22156212c9ddc0ff21a69b46302c3fde2d9018583f21144d3082542f6588'
assert all(checks.values()),checks
names=subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines()
stages=[name for name in names if re.fullmatch(r'moara-project-files-stage-[0-9a-f]{10}',name)]
if stages:subprocess.run(['docker','stop',*stages],check=True,stdout=subprocess.DEVNULL)
report={'published':True,'tested_image_id':image,'unit_tests':tests['tests'],'checks':checks,'inference':inference,'changed_backend_modules':sorted(changed),'stopped_preserved_candidates':stages,'database_migrations':False}
(root/'docs/runtime/project-files-final.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
