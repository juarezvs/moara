import pathlib,json,shutil,subprocess
root=pathlib.Path(__file__).resolve().parents[2];tag='moara-core:careers-20261031'
for container,base in [('ai-server-moara-legal-mcp-1','moara-core:pre-careers-mcp-20261031'),('ai-server-moara-gateway-1','moara-core:pre-careers-app-20261031')]:
 if subprocess.run(['docker','image','inspect',base],capture_output=True).returncode:
  current=subprocess.check_output(['docker','inspect',container,'--format','{{.Image}}'],text=True).strip();subprocess.run(['docker','tag',current,base],check=True)
folder=root/'tmp/careers-build';folder.mkdir(exist_ok=True);dockerfile='FROM moara-core:pre-careers-mcp-20261031\n'
for name in ['discovery.py','research.py','server.py']:
 shutil.copyfile(root/'moara/legal_mcp'/name,folder/name);dockerfile+='COPY '+name+' /app/moara/legal_mcp/'+name+'\n'
shutil.copyfile(root/'moara/gateway/legal_answer.py',folder/'legal_answer.py');dockerfile+='COPY legal_answer.py /app/moara/gateway/legal_answer.py\n'
(folder/'Dockerfile').write_text(dockerfile);subprocess.run(['docker','build','--network','none','-t',tag,str(folder)],check=True)
tests=folder/'tests';shutil.copytree(root/'tmp/google-discovery-build/tests',tests,dirs_exist_ok=True);shutil.copyfile(root/'moara/tests/test_career_discovery.py',tests/'test_career_discovery.py')
subprocess.run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL','-v',str(tests)+':/tests:ro','--entrypoint','python',tag,'-m','unittest','discover','-s','/tests','-v'],check=True)
source=(root/'infrastructure/legal/stage_grounding.py').read_text().replace('moara-core:legal-grounding-20261031',tag).replace('moara-legal-grounding-stage-','moara-careers-mcp-stage-').replace('moara-legal-app-grounding-stage-','moara-careers-app-stage-').replace('tmp/legal-grounding-stage.json','tmp/careers-stage.json')
exec(compile(source,'stage_careers','exec'),{'__file__':str(root/'infrastructure/legal/stage_grounding.py')})
