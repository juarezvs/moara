"""Build and test against a preserved running image; no package/model upgrades."""
import json,pathlib,shutil,subprocess
root=pathlib.Path(__file__).resolve().parents[2]
tag='moara-core:2.0-foundation-20261030';base='moara-core:pre-moara2-20261030'
def run(args):subprocess.run(args,check=True)
if subprocess.run(['docker','image','inspect',base],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
    current=json.loads(subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1']))[0]['Image']
    run(['docker','tag',current,base])
context=root/'tmp/moara2-build';context.mkdir(exist_ok=True)
for directory in ['moara/identity','moara/assistants','moara/web/dist/moara-web/browser']:
    shutil.copytree(root/directory,context/directory,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
files=['api.py','chat_api.py','history_api.py','platform_runs.py','assistants.py','orchestration.py','official_integrations.py','chat_evidence.py','data_chat.py','settings.py','legal_verification.py','accessibility_api.py','inference_status.py','platform_documents.py','xlsx_documents.py']
files=['moara/gateway/'+name for name in files]+[
 'moara/gateway/migrations/008_official_assistants.sql','moara/gateway/migrations/009_chat_assistant_context.sql',
 'moara/gateway/alembic/versions/0008_official_assistants.py','moara/gateway/alembic/versions/0009_chat_assistant_context.py']
for name in files:
    destination=context/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,destination)
shutil.copyfile(root/'infrastructure/moara2/Dockerfile',context/'Dockerfile')
run(['docker','build','--network','none','--build-arg','BASE_IMAGE='+base,'-t',tag,str(context)])
tests=root/'tmp/moara2-tests';tests.mkdir(exist_ok=True)
for name in ['test_legal_verification.py','test_moara2.py','test_gpu_reranking.py','test_xlsx_documents.py']:
    shutil.copyfile(root/'moara/tests'/name,tests/name)
run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL',
 '-v',str(tests)+':/tests:ro','--entrypoint','python',tag,'-m','unittest','discover','-s','/tests','-v'])
print('MOARA2_FOUNDATION_BUILD_TESTED',flush=True)
