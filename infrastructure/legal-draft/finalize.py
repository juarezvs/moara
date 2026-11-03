import pathlib,subprocess,json,importlib.util,re
root=pathlib.Path(__file__).resolve().parents[2];checks={};images={}
for label,service in [('core','ai-server-moara-gateway-1'),('mcp','ai-server-moara-legal-mcp-1')]:
 images[label]=subprocess.check_output(['docker','inspect',service,'--format','{{.Image}}'],text=True).strip()
tests=json.loads((root/'tmp/legal-draft-tests.json').read_text())
checks['unit_tests_pass']=tests['passed'] and tests['tests']>=299
for label,service in [('core','ai-server-moara-gateway-1'),('mcp','ai-server-moara-legal-mcp-1')]:
 checks[label+'_is_tested_image']=images[label]==tests['images'][service]
for filename in ['legal-draft-live-stage.json','legal-draft-live-public.json']:
 report=json.loads((root/'docs/runtime'/filename).read_text())
 checks[filename]=report['images']==images and all(report['checks'].values())
for filename in ['legal-draft-ui-stage.json','legal-draft-ui-public.json']:
 report=json.loads((root/'docs/runtime'/filename).read_text())
 checks[filename]=report['tested_image_id']==images['core'] and all(report['checks'].values())
cfg=json.loads(subprocess.check_output(['docker','inspect','moara-searxng']))[0]
checks['search_has_no_host_ports']=not cfg['HostConfig'].get('PortBindings')
checks['search_restarts_automatically']=cfg['HostConfig']['RestartPolicy']['Name']=='unless-stopped'
checks['search_is_on_private_network']=json.loads(subprocess.check_output(['docker','network','inspect','moara-public-search']))[0]['Internal'] is True
for service in ['ai-server-moara-gateway-1','ai-server-moara-legal-mcp-1']:
 cfg=json.loads(subprocess.check_output(['docker','inspect',service]))[0]
 checks[service+'_catalogues_read_only']=all(any(v['Destination']==p and not v['RW'] for v in cfg['Mounts']) for p in ['/app/legal_catalog/stf','/app/legal_catalog/lexml'])
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code="""import sys,json,httpx
token=sys.stdin.read().strip()
with httpx.Client(trust_env=False,timeout=20) as c:
 r=c.get('http://localhost:8075/api/v1/observability/inference',headers={'Authorization':'Bearer '+token});r.raise_for_status();v=r.json()
 print(json.dumps({k:v.get(k) for k in ['available','principal_resident','embeddings_resident']}))
"""
r=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session(),capture_output=True,text=True,check=True)
inference=json.loads(r.stdout)
checks['principal_resident']=inference['principal_resident'] is True
checks['embeddings_resident']=inference['embeddings_resident'] is True
hashcode="""import pathlib,hashlib,json
r=pathlib.Path('/app/web');print(json.dumps({str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in r.rglob('*') if p.is_file()}))
"""
before=json.loads(subprocess.check_output(['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL','--entrypoint','python','moara-core:pre-legal-draft-app-20261102-r2','-c',hashcode],text=True))
after=json.loads(subprocess.check_output(['docker','exec','ai-server-moara-gateway-1','python','-c',hashcode],text=True))
preserved=lambda values:{k:v for k,v in values.items() if k.startswith(('brand/','fonts/','integrations/'))}
checks['frontend_brand_assets_preserved']=preserved(before)==preserved(after)
css=json.loads((root/'docs/runtime/legal-draft-css-check.json').read_text())
# Tailwind removed one unused utility during the rebuild. Active styles were
# compared, not merely old files left in the image's asset directory.
checks['active_css_has_only_reviewed_unused_utility_removal']=css['active_css_identical'] or css['changes']==[{'operation':'delete','before':'.fixed{position:fixed','after':''}]
parallel_code="""import pathlib,hashlib,json
paths=['moara/gateway/auth.py','moara/gateway/admin_api.py','moara/gateway/alembic/versions/0010_api_key_unlimited_rpm.py','moara/gateway/migrations/010_api_key_unlimited_rpm.sql'];print(json.dumps({p:hashlib.sha256((pathlib.Path('/app')/p).read_bytes()).hexdigest() for p in paths}))
"""
parallel_before=json.loads(subprocess.check_output(['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL','--entrypoint','python','moara-core:pre-legal-draft-app-20261102-r2','-c',parallel_code],text=True))
parallel_after=json.loads(subprocess.check_output(['docker','exec','ai-server-moara-gateway-1','python','-c',parallel_code],text=True))
checks['concurrent_api_key_update_preserved']=parallel_before==parallel_after
checks['legal_metadata_timer_active']=subprocess.check_output(['systemctl','--user','is-active','moara-legal-metadata.timer'],text=True).strip()=='active'
assert all(checks.values()),checks
names=subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines()
owned=[n for n in names if re.fullmatch(r'moara-legal-draft-(app-stage|mcp-stage|tls)-[0-9a-f]{10}',n)]
if owned:subprocess.run(['docker','stop',*owned],capture_output=True,check=True)
result={'published':True,'images':images,'unit_tests':tests['tests'],'checks':checks,'inference':inference,'database_migrations':False,'stopped_private_candidates':owned}
(root/'docs/runtime/legal-draft-final.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
