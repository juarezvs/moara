import pathlib,subprocess,json,base64,gzip,hashlib
root=pathlib.Path(__file__).resolve().parents[2]
def image(container):return subprocess.check_output(['docker','inspect',container,'--format','{{.Image}}'],text=True).strip()
mcp_image=image('ai-server-moara-legal-mcp-1');app_image=image('ai-server-moara-gateway-1')
for filename in ['google-discovery-stage.json','google-discovery-public.json']:
 d=json.loads((root/'docs/runtime'/filename).read_text());assert d['tested_mcp_image']==mcp_image and all(d['checks'].values())
 p=d['provider_result'];assert p['normative_evidence'] is False and p['generated_answer_used'] is False
 raw=gzip.decompress(base64.b64decode(p['robots']['snapshot_gzip_base64']));assert hashlib.sha256(raw).hexdigest()==p['robots']['sha256']
 assert p['status']=='provider_access_restricted' and any(x['url']=='https://www.google.com/search' for x in p['navigation_checks'])
for filename in ['google-app-stage.json','google-app-public.json']:
 d=json.loads((root/'docs/runtime'/filename).read_text());assert all(d['checks'].values());assert d['tested_image_id']==(mcp_image if 'stage' in filename else app_image)
for n in ['ai-server-moara-google-browser-1']:
 d=json.loads(subprocess.check_output(['docker','inspect',n]))[0];assert not d['HostConfig'].get('PortBindings')
 assert set(d['NetworkSettings']['Networks'])=={'ai-server_moara_research_browser','ai-server_moara_search_egress'}
code="""import asyncio,json,httpx
from moara.gateway.settings import Settings
async def main():
 s=Settings.load()
 async with httpx.AsyncClient(trust_env=False,timeout=20) as c:
  r=await c.get(s.legal_mcp_url.rsplit('/mcp',1)[0]+'/health');r.raise_for_status();assert r.json()['version']=='0.8.0'
  r=await c.get(s.legacy_gateway+'/v1/inference/status',headers={'Authorization':'Bearer '+s.llm_key});r.raise_for_status();d=r.json();assert d['principal_resident']
  print(json.dumps({'principal_resident':d['principal_resident'],'embeddings_resident':d.get('embeddings_resident')}))
asyncio.run(main())"""
r=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c',code],capture_output=True,text=True,check=True);health=json.loads(r.stdout)
stopped=[]
for name in subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines():
 if name.startswith(('moara-google-browser-stage-','moara-google-mcp-stage-','moara-google-app-stage-')):
  d=json.loads(subprocess.check_output(['docker','inspect',name]))[0];assert not d['HostConfig'].get('PortBindings');subprocess.run(['docker','stop',name],check=True,capture_output=True);stopped.append(name)
for filename in ['README.md','docs/PROJECT_STATUS.md','docs/MOARA_2_OPERATIONS.md']:
 p=root/filename;target=('docs/' if filename=='README.md' else '')+'MOARA_GOOGLE_DISCOVERY_2026-10-31.md'
 if target not in p.read_text():
  with p.open('a') as out:out.write('\n\n[Descoberta web e restrição observada no Google Modo IA]('+target+').\n')
result={'integration_published':True,'mcp_version':'0.8.0','mcp_image':mcp_image,'gateway_image_unchanged':app_image,'google_search_operational':False,'provider_status':'provider_access_restricted','unit_tests':173,'official_application_checks':True,'policy_snapshot_reproduced':True,'browser_port_unpublished':True,'browser_isolated_from_institutional_networks':True,'inference_restarted':False,**health,'preserved_stopped_candidates':stopped}
(root/'docs/runtime/google-discovery-final.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
