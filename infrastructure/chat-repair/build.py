"""Patch conversational intent while preserving the current workspace and runtime."""
import pathlib,subprocess,json,shutil
root=pathlib.Path(__file__).resolve().parents[2]
base='moara-core:pre-chat-intent-20261030';tag='moara-core:chat-intent-20261030'
if subprocess.run(['docker','image','inspect',base],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
    current=json.loads(subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1']))[0]['Image']
    subprocess.run(['docker','tag',current,base],check=True)
context=root/'tmp/chat-intent-build';context.mkdir(exist_ok=True)
files=['moara/identity/service.py','moara/gateway/institutional.py','moara/gateway/orchestration.py','moara/gateway/legal_verification.py','moara/gateway/chat_api.py','moara/gateway/context_budget.py','moara/gateway/client_documents.py','moara/gateway/chat_evidence.py']
dockerfile='FROM '+base+'\n'
for name in files:
    target=context/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,target)
    dockerfile+='COPY '+name+' /app/'+name+'\n'
(context/'Dockerfile').write_text(dockerfile)
subprocess.run(['docker','build','--network','none','-t',tag,str(context)],check=True)
tests=context/'tests';tests.mkdir(exist_ok=True)
for name in ['test_moara2.py','test_legal_verification.py','test_gpu_reranking.py','test_xlsx_documents.py','test_chat_intent_repair.py','test_context_budget.py','test_client_documents.py']:
    shutil.copyfile(root/'moara/tests'/name,tests/name)
subprocess.run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL',
    '-v',str(tests)+':/tests:ro','--entrypoint','python',tag,'-m','unittest','discover','-s','/tests','-v'],check=True)
print('CHAT_INTENT_REPAIR_UNIT_TESTS_PASSED')
