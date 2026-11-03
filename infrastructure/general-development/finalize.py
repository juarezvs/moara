import pathlib,subprocess,json,importlib.util,re,ssl,urllib.request,urllib.parse
root=pathlib.Path(__file__).resolve().parents[2]
image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
checks={}
for filename in ['general-development-stage.json','general-development-public.json','general-development-self-stage.json','general-development-self-public.json','general-development-legal-stage.json','general-development-legal-public.json','general-development-preservation.json','general-development-project.json']:
 d=json.loads((root/'docs/runtime'/filename).read_text());checks[filename]=d['tested_image_id']==image and all(d['checks'].values())
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code="""import sys,httpx,json
token=sys.stdin.read().strip()
with httpx.Client(trust_env=False,timeout=20) as c:
 r=c.get('http://localhost:8075/api/v1/observability/inference',headers={'Authorization':'Bearer '+token});r.raise_for_status();v=r.json()
 print(json.dumps({'available':v.get('available'),'principal_resident':v.get('principal_resident'),'embeddings_resident':v.get('embeddings_resident')}))
"""
r=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session(),text=True,capture_output=True,check=True)
inference=json.loads(r.stdout);checks['principal_resident']=inference['principal_resident'] is True;checks['embeddings_resident']=inference['embeddings_resident'] is True
checks['metadata_timer_active']=subprocess.check_output(['systemctl','--user','is-active','moara-legal-metadata.timer'],text=True).strip()=='active'
tls=ssl.create_default_context()
for name in ['ai-root-ca.crt','moara-domain-root-ca.crt']:tls.load_verify_locations(cafile=str(root/'docs/runtime'/name))
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=tls))
with opener.open('https://moara.am.trf1.gov.br/',timeout=20) as response:
 checks['public_root_opens_current_chat']=response.status==200 and urllib.parse.urlsplit(response.url).path=='/moara/chat'
for name in ['ai-server-moara-gateway-1','ai-server-moara-legal-mcp-1']:
 cfg=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
 checks[name+'_tested_image']=cfg['Image']==(image if name.endswith('gateway-1') else subprocess.check_output(['docker','image','inspect','moara-core:pre-general-development-mcp-20261102','--format','{{.Id}}'],text=True).strip())
 checks[name+'_read_only_catalogs']=all(any(v['Destination']==p and not v['RW'] for v in cfg['Mounts']) for p in ['/app/legal_catalog/stf','/app/legal_catalog/lexml'])
assert all(checks.values()),checks
names=subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines()
stages=[name for name in names if re.fullmatch('moara-general-development-(app|mcp)-stage-[0-9a-f]{10}',name)]
if stages:subprocess.run(['docker','stop',*stages],check=True,stdout=subprocess.DEVNULL)
report={'published':True,'tested_image_id':image,'checks':checks,'unit_tests':json.loads((root/'tmp/general-development-tests.json').read_text())['tests'],'stopped_preserved_candidates':stages}
(root/'docs/runtime/general-development-final.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
