import pathlib,json,subprocess,shutil
root=pathlib.Path(__file__).resolve().parents[2]
image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
for name in ['citations-ui-stage.json','citations-ui-public.json']:
 d=json.loads((root/'docs/runtime'/name).read_text());assert d['tested_image_id']==image and all(d['checks'].values())
 if name.endswith('public.json'):
  folder=root/'infrastructure/site-entry'/('unified-output-'+d['test_container'].rsplit('-',1)[1])
  for screenshot in ['citations-desktop.png','citations-mobile.png']:shutil.copyfile(folder/screenshot,root/'docs/runtime'/screenshot)
mcp=subprocess.check_output(['docker','inspect','ai-server-moara-legal-mcp-1','--format','{{.Image}}'],text=True).strip()
assert mcp==subprocess.check_output(['docker','image','inspect','moara-core:pre-citations-20261031','--format','{{.Id}}'],text=True).strip()
stopped=[]
for n in subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines():
 if n.startswith(('moara-citations-stage-','moara-unified-proxy-stage-')):
  info=json.loads(subprocess.check_output(['docker','inspect',n]))[0];assert not info['HostConfig'].get('PortBindings');subprocess.run(['docker','stop',n],check=True,capture_output=True);stopped.append(n)
for filename in ['README.md','docs/PROJECT_STATUS.md','docs/MOARA_2_OPERATIONS.md']:
 p=root/filename;target=('docs/' if filename=='README.md' else '')+'MOARA_SOURCE_HINTS_2026-10-31.md'
 if target not in p.read_text():
  with p.open('a') as out:out.write('\n\n[Fontes junto aos trechos e painel de consulta]('+target+').\n')
result={'published':True,'image':image,'mcp_unchanged':True,'inference_restarted':False,'preserved_stopped_candidates':stopped}
(root/'docs/runtime/citations-final.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
