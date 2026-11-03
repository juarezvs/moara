"""IDE keys/API and portal on the preserved current Moara production image."""
import pathlib,subprocess,shutil,json
root=pathlib.Path(__file__).resolve().parents[2]
base='moara-core:pre-unified-20261031';tag='moara-core:unified-20261031'
if subprocess.run(['docker','image','inspect',base],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
 current=json.loads(subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1']))[0]['Image']
 subprocess.run(['docker','tag',current,base],check=True)
folder=root/'tmp/unified-build';folder.mkdir(exist_ok=True)
dockerfile='FROM '+base+'\n'
for name in ['api.py','previous_history.py','auth.py','auth_api.py']:
 source=root/'moara/gateway'/name;target=folder/'moara/gateway'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
 dockerfile+='COPY moara/gateway/'+name+' /app/moara/gateway/'+name+'\n'
shutil.copytree(root/'moara/web/dist/moara-web/browser',folder/'web',dirs_exist_ok=True)
dockerfile+='COPY web /app/web\n';(folder/'Dockerfile').write_text(dockerfile)
subprocess.run(['docker','build','--network','none','-t',tag,str(folder)],check=True)
tests=folder/'tests';tests.mkdir(exist_ok=True)
for name in ['test_moara2.py','test_legal_verification.py','test_gpu_reranking.py','test_xlsx_documents.py','test_chat_intent_repair.py','test_context_budget.py','test_client_documents.py','test_chat_progress.py','test_legal_catalog.py','test_developer_api.py','test_legal_information.py','test_legal_grounding.py','test_unified_chat.py']:
 shutil.copyfile(root/'moara/tests'/name,tests/name)
subprocess.run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL','-v',str(tests)+':/tests:ro','--entrypoint','python',tag,'-m','unittest','discover','-s','/tests','-v'],check=True)
print('IDE_BUILD_AND_UNIT_TESTS_PASSED')
