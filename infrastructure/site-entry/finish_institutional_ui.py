import pathlib,subprocess,json,shutil
root=pathlib.Path(__file__).resolve().parents[2];image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
for name in ['institutional-ui-stage.json','institutional-ui-public.json','institutional-reading-ui-stage.json','institutional-reading-ui-public.json','institutional-code-stage.json','institutional-code-public.json']:
 r=json.loads((root/'docs/runtime'/name).read_text());assert r['tested_image_id']==image and r['checks'] and all(r['checks'].values())
 if name=='institutional-ui-public.json':
  folder=root/'infrastructure/site-entry'/('unified-output-'+r['test_container'].rsplit('-',1)[1])
  for mode in ['desktop','dark','mobile']:shutil.copyfile(folder/('institutional-home-'+mode+'.png'),root/'docs/runtime'/('institutional-home-'+mode+'.png'))
 if name=='institutional-reading-ui-public.json':
  folder=root/'infrastructure/site-entry'/('unified-output-'+r['test_container'].rsplit('-',1)[1])
  for mode in ['desktop','mobile']:shutil.copyfile(folder/('chat-reading-'+mode+'.png'),root/'docs/runtime'/('institutional-chat-'+mode+'.png'))
code=json.loads((root/'docs/runtime/institutional-code-public.json').read_text())
names=subprocess.check_output(['docker','ps','-a','--format','{{.Names}}'],text=True).splitlines();suffixes=[n.rsplit('-',1)[1] for n in names if n.startswith('moara-institutional-ui-stage-')];stopped=[]
for name in subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines():
 if name.startswith('moara-institutional-ui-stage-') or any(name.startswith('moara-unified-proxy-stage-'+s+'-') for s in suffixes):
  info=json.loads(subprocess.check_output(['docker','inspect',name]))[0];assert not info['HostConfig'].get('PortBindings');subprocess.run(['docker','stop',name],check=True,capture_output=True);stopped.append(name)
result={'published':True,'image':image,'frontend_only':True,'design_checks':len(json.loads((root/'docs/runtime/institutional-ui-public.json').read_text())['checks']),'conversation_checks':len(json.loads((root/'docs/runtime/institutional-reading-ui-public.json').read_text())['checks']),'preservation_checks':len(code['checks']),'backend_source_unchanged':code['checks']['backend_source_unchanged'],'mcp_image_unchanged':code['checks']['mcp_service_image_unchanged'],'principal_resident':code['principal_resident'],'embeddings_resident':code['embeddings_resident'],'metadata_timer_preserved':code['checks']['metadata_timer_active'],'preserved_stopped_candidates':stopped}
(root/'docs/runtime/institutional-ui-final.json').write_text(json.dumps(result,indent=2))
for filename in ['README.md','docs/PROJECT_STATUS.md','docs/MOARA_2_OPERATIONS.md']:
 p=root/filename;target=('docs/' if filename=='README.md' else '')+'MOARA_INSTITUTIONAL_DESIGN_2026-10-31.md'
 if target not in p.read_text():
  with p.open('a') as out:out.write('\n\n[Interface institucional propria da Moara]('+target+').\n')
print(json.dumps(result))
