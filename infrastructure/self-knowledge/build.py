import pathlib,subprocess,json,shutil,re
root=pathlib.Path(__file__).resolve().parents[2];tag='moara-core:self-knowledge-20261102'
for service,base in [('ai-server-moara-gateway-1','moara-core:pre-self-knowledge-app-20261102'),('ai-server-moara-legal-mcp-1','moara-core:pre-self-knowledge-mcp-20261102')]:
 if subprocess.run(['docker','image','inspect',base],capture_output=True).returncode:
  image=subprocess.check_output(['docker','inspect',service,'--format','{{.Image}}'],text=True).strip();subprocess.run(['docker','tag',image,base],check=True)
folder=root/'tmp/self-knowledge-build';folder.mkdir(exist_ok=True);dockerfile='FROM moara-core:pre-self-knowledge-app-20261102\n'
for name in ['moara/gateway/self_knowledge.py','moara/gateway/institutional.py','moara/gateway/orchestration.py','moara/gateway/chat_api.py']:
 target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,target);dockerfile+='COPY '+name+' /app/'+name+'\n'
(folder/'Dockerfile').write_text(dockerfile)
subprocess.run(['docker','build','--network','none','-t',tag,str(folder)],check=True)
tests=folder/'tests';shutil.copytree(root/'tmp/explanation-build/tests',tests,dirs_exist_ok=True);shutil.copyfile(root/'moara/tests/test_self_knowledge.py',tests/'test_self_knowledge.py')
shutil.copyfile(root/'moara/tests/test_legal_recovery.py',tests/'test_legal_recovery.py')
r=subprocess.run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL','-v',str(tests)+':/tests:ro','--entrypoint','python',tag,'-m','unittest','discover','-s','/tests','-v'],capture_output=True,text=True);print(r.stdout+r.stderr,flush=True)
image=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip();match=re.search(r'Ran (\d+) tests',r.stdout+r.stderr)
(root/'tmp/self-knowledge-tests.json').write_text(json.dumps({'passed':r.returncode==0,'tests':int(match[1]) if match else None,'image':image}));r.check_returncode()
source=(root/'infrastructure/legal/stage_grounding.py').read_text().replace('moara-core:legal-grounding-20261031',tag).replace('moara-legal-grounding-stage-','moara-self-knowledge-mcp-stage-').replace('moara-legal-app-grounding-stage-','moara-self-knowledge-app-stage-').replace('tmp/legal-grounding-stage.json','tmp/self-knowledge-stage.json')
source=source.replace("args+=[image]+original['Config']['Cmd'];", "args+=['--mount',f'type=bind,src={root}/data/legal/stf-theses,dst=/app/legal_catalog/stf,readonly','--mount',f'type=bind,src={root}/data/legal/metadata,dst=/app/legal_catalog/lexml,readonly'];args+=[image]+original['Config']['Cmd'];")
exec(compile(source,'stage_chat_reading','exec'),{'__file__':str(root/'infrastructure/legal/stage_grounding.py')})
