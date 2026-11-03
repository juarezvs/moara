"""Official-source expansion on the exact preserved production runtime."""
import pathlib,subprocess,json,shutil
root=pathlib.Path(__file__).resolve().parents[2]
base='moara-core:pre-legal-sources-v2-20261030';tag='moara-core:legal-sources-v2-20261030'
if subprocess.run(['docker','image','inspect',base],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
 current=json.loads(subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1']))[0]['Image']
 subprocess.run(['docker','tag',current,base],check=True)
folder=root/'tmp/legal-sources-v2-build';folder.mkdir(exist_ok=True)
dockerfile='FROM '+base+'\n'
files=list((root/'moara/legal_mcp').glob('*.py'))+[root/'moara/gateway/legal_verification.py',root/'moara/gateway/settings.py']
for path in files:
 name=str(path.relative_to(root));target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
 dockerfile+='COPY '+name+' /app/'+name+'\n'
(folder/'Dockerfile').write_text(dockerfile)
subprocess.run(['docker','build','--network','none','-t',tag,str(folder)],check=True)
tests=folder/'tests';tests.mkdir(exist_ok=True)
for name in ['test_moara2.py','test_legal_verification.py','test_gpu_reranking.py','test_xlsx_documents.py','test_chat_intent_repair.py','test_context_budget.py','test_client_documents.py','test_chat_progress.py','test_legal_catalog.py']:
 shutil.copyfile(root/'moara/tests'/name,tests/name)
subprocess.run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL','-v',str(tests)+':/tests:ro','--entrypoint','python',tag,'-m','unittest','discover','-s','/tests','-v'],check=True)
print('LEGAL_SOURCES_V2_BUILD_AND_TESTS_PASSED')
