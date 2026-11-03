import pathlib,json,subprocess
root=pathlib.Path(__file__).resolve().parents[2];image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip();reports={}
for name in ['chat-scroll-ui-stage.json','chat-scroll-ui-public.json','chat-scroll-reading-stage.json','chat-scroll-reading-public.json','chat-scroll-code-stage.json','chat-scroll-code-public.json']:
 r=json.loads((root/'docs/runtime'/name).read_text());assert r['tested_image_id']==image and r['checks'] and all(r['checks'].values());reports[name]=r
names=subprocess.check_output(['docker','ps','-a','--format','{{.Names}}'],text=True).splitlines();suffixes=[n.rsplit('-',1)[1] for n in names if n.startswith('moara-chat-scroll-stage-')];stopped=[]
for name in subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines():
 if name.startswith('moara-chat-scroll-stage-') or any(name.startswith('moara-unified-proxy-stage-'+s+'-') for s in suffixes):
  info=json.loads(subprocess.check_output(['docker','inspect',name]))[0];assert not info['HostConfig'].get('PortBindings');subprocess.run(['docker','stop',name],check=True,capture_output=True);stopped.append(name)
code=reports['chat-scroll-code-public.json'];r={'published':True,'image':image,'controlled_scroll_checks':len(reports['chat-scroll-ui-public.json']['checks']),'real_conversation_checks':len(reports['chat-scroll-reading-public.json']['checks']),'preservation_checks':len(code['checks']),'backend_unchanged':code['checks']['backend_source_unchanged'],'mcp_unchanged':code['checks']['mcp_service_image_unchanged'],'principal_resident':code['principal_resident'],'embeddings_resident':code['embeddings_resident'],'stopped_preserved_candidates':stopped}
(root/'docs/runtime/chat-scroll-final.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
