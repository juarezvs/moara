import pathlib,subprocess,shutil
root=pathlib.Path(__file__).resolve().parents[2];tag='moara-core:legal-recovery-20261031'
for service,base in [('ai-server-moara-gateway-1','moara-core:pre-legal-recovery-20261031'),('ai-server-moara-legal-mcp-1','moara-core:pre-mcp-recovery-20261031')]:
 if subprocess.run(['docker','image','inspect',base],capture_output=True).returncode:
  current=subprocess.check_output(['docker','inspect',service,'--format','{{.Image}}'],text=True).strip();subprocess.run(['docker','tag',current,base],check=True)
folder=root/'tmp/legal-recovery-build';folder.mkdir(exist_ok=True);dockerfile='FROM moara-core:pre-legal-recovery-20261031\n'
for path in list((root/'moara/legal_mcp').glob('*.py'))+[root/'moara/gateway'/n for n in ['legal_verification.py','legal_answer.py','chat_progress.py','orchestration.py']]:
 name=str(path.relative_to(root));target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target);dockerfile+='COPY '+name+' /app/'+name+'\n'
(folder/'Dockerfile').write_text(dockerfile);subprocess.run(['docker','build','--network','none','-t',tag,str(folder)],check=True)
tests=folder/'tests';tests.mkdir(exist_ok=True)
for source in (root/'tmp/identity-rbac-build/tests').glob('test_*.py'):shutil.copyfile(source,tests/source.name)
for name in ['test_legal_catalog.py','test_legal_discovery.py','test_legal_recovery.py']:shutil.copyfile(root/'moara/tests'/name,tests/name)
subprocess.run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL','-v',str(tests)+':/tests:ro','--entrypoint','python',tag,'-m','unittest','discover','-s','/tests','-v'],check=True)
source=(root/'infrastructure/legal/stage_grounding.py').read_text().replace('moara-core:legal-grounding-20261031',tag).replace('moara-legal-grounding-stage-','moara-legal-recovery-stage-').replace('moara-legal-app-grounding-stage-','moara-legal-app-recovery-stage-').replace('tmp/legal-grounding-stage.json','tmp/legal-recovery-stage.json')
exec(compile(source,'stage_discovery','exec'),{'__file__':str(root/'infrastructure/legal/stage_grounding.py')})
