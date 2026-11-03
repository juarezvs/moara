import pathlib,subprocess,json,shutil
root=pathlib.Path('/home/nutec/ai-server')
def run(args):subprocess.run(args,check=True)
current=json.loads(subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1']))[0]['Image']
base='moara-core:pre-legal-20261030'
if subprocess.run(['docker','image','inspect',base],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
    run(['docker','tag',current,base])
context=root/'tmp/legal-build-context';context.mkdir(exist_ok=True)
paths=list((root/'moara/legal_mcp').glob('*.py'))+[root/p for p in [
 'moara/gateway/legal_verification.py','moara/gateway/chat_api.py','moara/gateway/platform_runs.py','moara/gateway/api.py',
 'moara/gateway/migrations/006_legal_evidence.sql','moara/gateway/alembic/versions/0006_legal_evidence.py',
 'moara/gateway/migrations/007_legal_evidence_guard.sql','moara/gateway/alembic/versions/0007_legal_evidence_guard.py']]
for source in paths:
 destination=context/source.relative_to(root);destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
shutil.copytree(root/'moara/web/dist/moara-web/browser',context/'moara/web/dist/moara-web/browser',dirs_exist_ok=True)
shutil.copyfile(root/'infrastructure/legal/Dockerfile',context/'Dockerfile')
run(['docker','build','--network','none','--build-arg','BASE_IMAGE='+base,'-t','moara-core:legal-20261030',str(context)])
run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:rw,size=64m','--cap-drop','ALL',
     '-v',str(root/'moara/tests/test_legal_verification.py')+':/tests/test_legal_verification.py:ro',
     '--entrypoint','python','moara-core:legal-20261030','-m','unittest','discover','-s','/tests','-p','test_legal_verification.py','-v'])
print('LEGAL_BUILD_AND_TESTS_PASSED',flush=True)
