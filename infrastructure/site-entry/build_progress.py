"""Narrow UI/progress release on the exact current production image."""
import pathlib,subprocess,json,shutil
root=pathlib.Path(__file__).resolve().parents[2]
base='moara-core:pre-work-progress-20261030';tag='moara-core:work-progress-20261030'
if subprocess.run(['docker','image','inspect',base],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
 current=json.loads(subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1']))[0]['Image']
 subprocess.run(['docker','tag',current,base],check=True)
folder=root/'tmp/work-progress-build';folder.mkdir(exist_ok=True)
dockerfile='FROM '+base+'\n'
for name in ['chat_api.py','chat_progress.py','chat_evidence.py','legal_verification.py']:
 src='moara/gateway/'+name;target=folder/src;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/src,target)
 dockerfile+='COPY '+src+' /app/'+src+'\n'
shutil.copytree(root/'moara/web/dist/moara-web/browser',folder/'web',dirs_exist_ok=True)
dockerfile+='COPY web /app/web\n';(folder/'Dockerfile').write_text(dockerfile)
subprocess.run(['docker','build','--network','none','-t',tag,str(folder)],check=True)
tests=folder/'tests';tests.mkdir(exist_ok=True)
for name in ['test_moara2.py','test_legal_verification.py','test_gpu_reranking.py','test_xlsx_documents.py','test_chat_intent_repair.py','test_context_budget.py','test_client_documents.py','test_chat_progress.py']:
 shutil.copyfile(root/'moara/tests'/name,tests/name)
subprocess.run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL','-v',str(tests)+':/tests:ro','--entrypoint','python',tag,'-m','unittest','discover','-s','/tests','-v'],check=True)
print('WORK_PROGRESS_BUILD_AND_TESTS_PASSED')
