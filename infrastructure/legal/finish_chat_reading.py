import pathlib,json,subprocess,shutil
root=pathlib.Path(__file__).resolve().parents[2]
image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
for filename in ['chat-reading-stage.json','chat-reading-public.json','chat-reading-ui-stage.json','chat-reading-ui-public.json','chat-reading-metadata-regression.json']:
 d=json.loads((root/'docs/runtime'/filename).read_text());assert d['tested_image_id']==image and d['checks'] and all(d['checks'].values())
 if filename=='chat-reading-ui-public.json':
  folder=root/'infrastructure/site-entry'/('unified-output-'+d['test_container'].rsplit('-',1)[1])
  for name in ['chat-reading-desktop.png','chat-reading-mobile.png']:shutil.copyfile(folder/name,root/'docs/runtime'/name)
test=json.loads((root/'tmp/chat-reading-tests.json').read_text());assert test['image']==image and test['passed']
for name in ['ai-server-moara-gateway-1','ai-server-moara-legal-mcp-1']:
 info=json.loads(subprocess.check_output(['docker','inspect',name]))[0];assert info['Image']==image
 for target in ['/app/legal_catalog/stf','/app/legal_catalog/lexml']:
  assert next(m for m in info['Mounts'] if m['Destination']==target)['RW'] is False
code="""import asyncio,json,httpx
from moara.gateway.settings import Settings
async def main():
 s=Settings.load()
 async with httpx.AsyncClient(trust_env=False,timeout=20) as c:
  r=await c.get(s.legacy_gateway+'/v1/inference/status',headers={'Authorization':'Bearer '+s.llm_key});r.raise_for_status();v=r.json();assert v['principal_resident'];print(json.dumps({'principal_resident':v['principal_resident'],'embeddings_resident':v.get('embeddings_resident')}))
asyncio.run(main())"""
r=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c',code],capture_output=True,text=True,check=True);health=json.loads(r.stdout)
subprocess.run(['systemctl','--user','is-active','--quiet','moara-legal-metadata.timer'],check=True)
names=subprocess.check_output(['docker','ps','-a','--format','{{.Names}}'],text=True).splitlines();suffixes=[n.rsplit('-',1)[1] for n in names if n.startswith('moara-chat-reading-app-stage-')];stopped=[]
for name in subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines():
 if name.startswith(('moara-chat-reading-app-stage-','moara-chat-reading-mcp-stage-')) or any(name.startswith('moara-unified-proxy-stage-'+s+'-') for s in suffixes):
  info=json.loads(subprocess.check_output(['docker','inspect',name]))[0];assert not info['HostConfig'].get('PortBindings');subprocess.run(['docker','stop',name],check=True,capture_output=True);stopped.append(name)
for filename in ['README.md','docs/PROJECT_STATUS.md','docs/MOARA_2_OPERATIONS.md']:
 p=root/filename;target=('docs/' if filename=='README.md' else '')+'MOARA_CHAT_READING_2026-10-31.md'
 if target not in p.read_text():
  with p.open('a') as out:out.write('\n\n[Leitura do chat e teses oficiais do STF]('+target+').\n')
answer=json.loads((root/'docs/runtime/chat-reading-public.json').read_text())
result={'published':True,'image':image,'unit_tests':test['tests'],'real_case_themes':[r['reference']['number'] for r in answer['themes']],'fresh_official_theses':True,'question_answer_same_width':True,'desktop_and_mobile_validated':True,'metadata_timer_preserved':True,'read_only_catalogues_preserved':True,'inference_restarted':False,**health,'preserved_stopped_candidates':stopped}
(root/'docs/runtime/chat-reading-final.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
