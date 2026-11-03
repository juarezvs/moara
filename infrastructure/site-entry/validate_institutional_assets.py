"""Confirm this delivery changes the interface and preserves running services."""
import pathlib,subprocess,json,sys,hashlib
root=pathlib.Path(__file__).resolve().parents[2];public='--public' in sys.argv
target='ai-server-moara-gateway-1' if public else json.loads((root/'tmp/institutional-ui-stage.json').read_text())['core']
code="""from pathlib import Path
import hashlib,json,urllib.request
root=Path('/app/moara');h=hashlib.sha256();files=sorted(root.rglob('*.py'))
for p in files:h.update(str(p.relative_to(root)).encode()+b'\\0'+p.read_bytes()+b'\\0')
assert urllib.request.urlopen('http://localhost:8075/api/v1/ready',timeout=10).status==200
print(json.dumps({'backend_digest':h.hexdigest(),'python_files':len(files)}))"""
def fingerprint(name):return json.loads(subprocess.check_output(['docker','exec',name,'python','-c',code],text=True))
current=fingerprint(target);image=subprocess.check_output(['docker','inspect',target,'--format','{{.Image}}'],text=True).strip()
mcp=json.loads(subprocess.check_output(['docker','inspect','ai-server-moara-legal-mcp-1']))[0]
if public:
 baseline=json.loads((root/'docs/runtime/institutional-code-stage.json').read_text());old=baseline['baseline_backend'];old_mcp=baseline['baseline_mcp_image']
else:old=fingerprint('ai-server-moara-gateway-1');old_mcp=mcp['Image']
checks={'application_ready':True,'backend_source_unchanged':current==old,'mcp_service_image_unchanged':mcp['Image']==old_mcp}
for name in [target,'ai-server-moara-legal-mcp-1']:
 info=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
 checks['catalogues_read_only_'+('gateway' if name==target else 'mcp')]=all(any(m['Destination']==dest and m['RW'] is False for m in info['Mounts']) for dest in ['/app/legal_catalog/stf','/app/legal_catalog/lexml'])
checks['metadata_timer_active']=subprocess.run(['systemctl','--user','is-active','--quiet','moara-legal-metadata.timer']).returncode==0
health="""import asyncio,json,httpx
from moara.gateway.settings import Settings
async def main():
 s=Settings.load()
 async with httpx.AsyncClient(trust_env=False,timeout=20) as c:
  r=await c.get(s.legacy_gateway+'/v1/inference/status',headers={'Authorization':'Bearer '+s.llm_key});r.raise_for_status();d=r.json();print(json.dumps({'principal_resident':d['principal_resident'],'embeddings_resident':d.get('embeddings_resident')}))
asyncio.run(main())"""
resident=json.loads(subprocess.check_output(['docker','exec',target,'python','-c',health],text=True));checks['principal_model_still_resident']=resident['principal_resident']
result={'checks':checks,'tested_image_id':image,'baseline_backend':old,'backend':current,'baseline_mcp_image':old_mcp,**resident}
(root/'docs/runtime'/('institutional-code-public.json' if public else 'institutional-code-stage.json')).write_text(json.dumps(result,indent=2));print(json.dumps(result));assert all(checks.values())
