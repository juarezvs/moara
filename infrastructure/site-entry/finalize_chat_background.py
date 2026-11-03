import pathlib,json,subprocess,re
root=pathlib.Path(__file__).resolve().parents[2]
image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
checks={}
for name in ['chat-background-ui-stage.json','chat-background-ui-public.json','chat-background-code-stage.json']:
 d=json.loads((root/'docs/runtime'/name).read_text());checks[name]=d['tested_image_id']==image and bool(d['checks']) and all(d['checks'].values())
preserved=json.loads((root/'docs/runtime/chat-background-code-stage.json').read_text())
checks['mcp_unchanged']=subprocess.check_output(['docker','inspect','ai-server-moara-legal-mcp-1','--format','{{.Image}}'],text=True).strip()==preserved['mcp_image_before']
assert all(checks.values()),checks
core=json.loads((root/'tmp/chat-background-stage.json').read_text())['core']
assert re.fullmatch('moara-chat-background-stage-[0-9a-f]{10}',core)
proxy=(root/'tmp/unified-proxy-name.txt').read_text().strip()
names=[core]
if proxy.startswith('moara-unified-proxy-stage-'+core.split('-')[-1]+'-'):names.insert(0,proxy)
subprocess.run(['docker','stop',*names],check=True,stdout=subprocess.DEVNULL)
report={'published':True,'tested_image_id':image,'checks':checks,'backend_files_preserved':preserved['after']['python_files'],'stopped_preserved_candidates':names}
(root/'docs/runtime/chat-background-final.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
