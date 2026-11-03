import pathlib,json,subprocess
root=pathlib.Path(__file__).resolve().parents[2]
tag='moara-core:chat-background-20261102'
code="""import pathlib,hashlib,json
p=pathlib.Path('/app/moara');h=hashlib.sha256();count=0
for f in sorted(p.rglob('*.py')):
 h.update(str(f.relative_to(p)).encode());h.update(f.read_bytes());count+=1
assets={name:hashlib.sha256((pathlib.Path('/app/web/brand')/name).read_bytes()).hexdigest() for name in ['mark.svg','chat-bg.png']}
print(json.dumps({'backend_sha256':h.hexdigest(),'python_files':count,'brand_assets':assets}))
"""
def fingerprint(image):
 return json.loads(subprocess.check_output(['docker','run','--rm','--network','none','--read-only','--entrypoint','python',image,'-c',code],text=True))
before=fingerprint('moara-core:pre-chat-background-app-20261102');after=fingerprint(tag)
checks={'backend_and_identity_unchanged':before==after,'all_backend_modules_preserved':after['python_files']>=88,'original_background_preserved':before['brand_assets']==after['brand_assets']}
image=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip()
report={'checks':checks,'before':before,'after':after,'tested_image_id':image,'mcp_image_before':subprocess.check_output(['docker','inspect','ai-server-moara-legal-mcp-1','--format','{{.Image}}'],text=True).strip()}
(root/'docs/runtime/chat-background-code-stage.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));assert all(checks.values())
