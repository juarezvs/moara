import pathlib,subprocess,json
root=pathlib.Path(__file__).resolve().parents[2]
tag='moara-core:self-knowledge-20261102'
code="""import pathlib,hashlib,json
p=pathlib.Path('/app/web');h=hashlib.sha256()
for f in sorted(p.rglob('*')):
 if f.is_file():h.update(str(f.relative_to(p)).encode());h.update(f.read_bytes())
q=pathlib.Path('/app/moara');modules=hashlib.sha256();count=0
changed={'gateway/self_knowledge.py','gateway/institutional.py','gateway/orchestration.py','gateway/chat_api.py'}
for f in sorted(q.rglob('*.py')):
 relative=str(f.relative_to(q))
 if relative not in changed:modules.update(relative.encode());modules.update(f.read_bytes());count+=1
print(json.dumps({'sha256':h.hexdigest(),'files':sum(f.is_file() for f in p.rglob('*')),'other_python_sha256':modules.hexdigest(),'other_python_count':count}))
"""
def fingerprint(image):
 return json.loads(subprocess.check_output(['docker','run','--rm','--network','none','--read-only','--entrypoint','python',image,'-c',code],text=True))
before=fingerprint('moara-core:pre-self-knowledge-app-20261102');after=fingerprint(tag)
image=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip()
checks={'all_web_assets_identical':before==after,'premium_interface_preserved':before['files']>10,'chat_scrolling_code_preserved':before['sha256']==after['sha256'],'other_backend_capabilities_preserved':before['other_python_sha256']==after['other_python_sha256'] and before['other_python_count']>80}
report={'checks':checks,'before':before,'after':after,'tested_image_id':image}
(root/'docs/runtime/self-knowledge-preservation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));assert all(checks.values())
