import pathlib,subprocess,json,shutil,re,time
root=pathlib.Path(__file__).resolve().parents[2]
tag='moara-core:project-files-20261102';base='moara-core:pre-project-files-app-20261102'
original=json.loads(subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1']))[0]
if subprocess.run(['docker','image','inspect',base],capture_output=True).returncode:
 subprocess.run(['docker','tag',original['Image'],base],check=True)
folder=root/'tmp/project-files-build';folder.mkdir(exist_ok=True)
shutil.copytree(root/'moara/web/dist/moara-web/browser',folder/'web',dirs_exist_ok=True)
dockerfile='FROM '+base+'\nCOPY web /app/web\n'
for name in ['project_tree.py','project_agent.py','platform_development.py','platform_contracts.py','developer_api.py']:
 dest=folder/'moara/gateway'/name;dest.parent.mkdir(parents=True,exist_ok=True)
 shutil.copyfile(root/'moara/gateway'/name,dest)
 dockerfile+='COPY moara/gateway/'+name+' /app/moara/gateway/'+name+'\n'
(folder/'Dockerfile').write_text(dockerfile)
subprocess.run(['docker','build','--network','none','-t',tag,str(folder)],check=True)
tests=folder/'tests';shutil.copytree(root/'tmp/general-development-build/tests',tests,dirs_exist_ok=True)
shutil.copyfile(root/'moara/tests/test_project_files.py',tests/'test_project_files.py')
r=subprocess.run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL','-v',str(tests)+':/tests:ro','--entrypoint','python',tag,'-m','unittest','discover','-s','/tests','-v'],capture_output=True,text=True)
print(r.stdout+r.stderr,flush=True)
image=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip()
match=re.search(r'Ran (\d+) tests',r.stdout+r.stderr)
(root/'tmp/project-files-tests.json').write_text(json.dumps({'passed':r.returncode==0,'tests':int(match[1]) if match else None,'image':image}))
r.check_returncode()
source=(root/'infrastructure/site-entry/build_chat_background.py').read_text().replace('moara-core:chat-background-20261102',tag).replace('moara-core:pre-chat-background-app-20261102',base).replace('tmp/chat-background-build','tmp/project-files-stage-build').replace('moara-chat-background-stage-','moara-project-files-stage-').replace('tmp/chat-background-stage.json','tmp/project-files-stage.json')
source=source[source.index("image=subprocess.check_output"):]
exec(compile(source,'project_files_stage','exec'),globals())
