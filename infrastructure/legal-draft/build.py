"""Build on the exact published images, retaining the validated chat layout."""
import pathlib,subprocess,json,shutil,re,time
root=pathlib.Path(__file__).resolve().parents[2];folder=root/'tmp/legal-draft-build';folder.mkdir(exist_ok=True)
targets=[('ai-server-moara-gateway-1','moara-core:legal-draft-app-20261102','moara-core:pre-legal-draft-app-20261102-r2'),
         ('ai-server-moara-legal-mcp-1','moara-core:legal-draft-mcp-20261102','moara-core:pre-legal-draft-mcp-20261102')]
files=['moara/gateway/legal_drafting.py','moara/gateway/legal_verification.py','moara/gateway/legal_answer.py','moara/legal_mcp/texts.py']
for name in files:
 target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,target)
shutil.copytree(root/'moara/web/dist/moara-web/browser',folder/'web',dirs_exist_ok=True)
for service,tag,base in targets:
 if subprocess.run(['docker','image','inspect',base],capture_output=True).returncode:
  image=subprocess.check_output(['docker','inspect',service,'--format','{{.Image}}'],text=True).strip();subprocess.run(['docker','tag',image,base],check=True)
 dockerfile='FROM '+base+'\n'
 if service.endswith('gateway-1'):dockerfile+='COPY web /app/web\n'
 for name in files:
  if service.endswith('legal-mcp-1') and not name.startswith('moara/legal_mcp/'):continue
  dockerfile+='COPY '+name+' /app/'+name+'\n'
 (folder/'Dockerfile').write_text(dockerfile)
 subprocess.run(['docker','build','--network','none','-t',tag,str(folder)],check=True)
tests=folder/'tests';shutil.copytree(root/'tmp/public-web-build/tests',tests,dirs_exist_ok=True)
shutil.copyfile(root/'moara/tests/test_legal_drafting.py',tests/'test_legal_drafting.py')
tag=targets[0][1]
r=subprocess.run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL','-v',str(tests)+':/tests:ro','--entrypoint','python',tag,'-m','unittest','discover','-s','/tests','-v'],capture_output=True,text=True)
print(r.stdout+r.stderr,flush=True)
images={service:subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip() for service,tag,base in targets}
match=re.search(r'Ran (\d+) tests',r.stdout+r.stderr)
(root/'tmp/legal-draft-tests.json').write_text(json.dumps({'passed':r.returncode==0,'tests':int(match[1]) if match else None,'images':images}));r.check_returncode()
# Reuse the established private candidate isolation, replacing release names only.
source=(root/'infrastructure/web-search/build.py').read_text()
source=source[source.index('suffix=images'):].replace('public-web','legal-draft')
exec(compile(source,'legal_draft_stage','exec'),globals())
(root/'tmp/unified-core-name.txt').write_text(core)
