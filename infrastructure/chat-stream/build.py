import pathlib,subprocess,json,shutil,re,time
root=pathlib.Path(__file__).resolve().parents[2]
tag='moara-core:chat-stream-20261102';base='moara-core:pre-chat-stream-app-20261102'
original=json.loads(subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1']))[0]
if subprocess.run(['docker','image','inspect',base],capture_output=True).returncode:subprocess.run(['docker','tag',original['Image'],base],check=True)
folder=root/'tmp/chat-stream-build';folder.mkdir(exist_ok=True)
shutil.copytree(root/'moara/web/dist/moara-web/browser',folder/'web',dirs_exist_ok=True)
dockerfile='FROM '+base+'\nCOPY web /app/web\n'
for name in ['chat_api.py','chat_delivery.py']:
 shutil.copyfile(root/'moara/gateway'/name,folder/name);dockerfile+='COPY '+name+' /app/moara/gateway/'+name+'\n'
(folder/'Dockerfile').write_text(dockerfile)
subprocess.run(['docker','build','--network','none','-t',tag,str(folder)],check=True)
tests=folder/'tests';shutil.copytree(root/'tmp/project-files-build/tests',tests,dirs_exist_ok=True)
shutil.copyfile(root/'moara/tests/test_chat_delivery.py',tests/'test_chat_delivery.py')
r=subprocess.run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL','-v',str(tests)+':/tests:ro','--entrypoint','python',tag,'-m','unittest','discover','-s','/tests','-v'],capture_output=True,text=True)
print(r.stdout+r.stderr,flush=True)
image=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip();match=re.search(r'Ran (\d+) tests',r.stdout+r.stderr)
(root/'tmp/chat-stream-tests.json').write_text(json.dumps({'passed':r.returncode==0,'tests':int(match[1]) if match else None,'image':image}));r.check_returncode()
source=(root/'infrastructure/site-entry/build_chat_background.py').read_text().replace('moara-chat-background-stage-','moara-chat-stream-stage-').replace('tmp/chat-background-stage.json','tmp/chat-stream-stage.json')
source=source[source.index('image=subprocess.check_output'):]
source=source.replace("'frontend_only':True","'frontend_only':False")
exec(compile(source,'chat_stream_stage','exec'),globals())
stage=json.loads((root/'tmp/chat-stream-stage.json').read_text());(root/'tmp/unified-core-name.txt').write_text(stage['core'])
