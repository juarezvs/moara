import pathlib,subprocess,shutil
root=pathlib.Path(__file__).resolve().parents[2]
base='moara-core:pre-identity-rbac-20261031';tag='moara-core:identity-rbac-20261031'
if subprocess.run(['docker','image','inspect',base],capture_output=True).returncode:
 current=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
 subprocess.run(['docker','tag',current,base],check=True)
folder=root/'tmp/identity-rbac-build';folder.mkdir(exist_ok=True)
dockerfile='FROM '+base+'\n'
for name in ['rbac.py','auth.py','admin_api.py','catalog_api.py']:
 target=folder/name;shutil.copyfile(root/'moara/gateway'/name,target)
 dockerfile+='COPY '+name+' /app/moara/gateway/'+name+'\n'
shutil.copytree(root/'moara/web/dist/moara-web/browser',folder/'web',dirs_exist_ok=True)
(folder/'Dockerfile').write_text(dockerfile+'COPY web /app/web\n')
subprocess.run(['docker','build','--network','none','-t',tag,str(folder)],check=True)
tests=folder/'tests';tests.mkdir(exist_ok=True)
for source in (root/'tmp/unified-build/tests').glob('test_*.py'):shutil.copyfile(source,tests/source.name)
shutil.copyfile(root/'moara/tests/test_identity_rbac.py',tests/'test_identity_rbac.py')
subprocess.run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL','-v',str(tests)+':/tests:ro','--entrypoint','python',tag,'-m','unittest','discover','-s','/tests','-v'],check=True)
source=(root/'infrastructure/site-entry/stage_unified.py').read_text().replace("image='moara-core:unified-20261031'","image='"+tag+"'")
exec(compile(source,'stage_identity_rbac','exec'),{'__file__':str(root/'infrastructure/site-entry/stage_unified.py')})
