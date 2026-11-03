"""Narrow offline build on the current preserved production gateway image."""
import pathlib,subprocess,json,shutil
root=pathlib.Path(__file__).resolve().parents[2];work=root/'tmp/gpu-tls-build';work.mkdir(exist_ok=True)
def run(args):subprocess.run(args,check=True)
base='ai-gateway:pre-mtls-20261030'
if subprocess.run(['docker','image','inspect',base],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
    current=json.loads(subprocess.check_output(['docker','inspect','ai-server-gateway-1']))[0]['Image']
    run(['docker','tag',current,base])
(work/'Dockerfile').write_text('FROM '+base+'\nCOPY app.py gpu_backend.py /app/\n')
for name in ['app.py','gpu_backend.py']:shutil.copyfile(root/'gateway/fastapi'/name,work/name)
run(['docker','build','--network','none','-t','ai-gateway:mtls-20261030',str(work)])
tests=work/'workspace'
for name in ['tests/operations/test_gpu_backend.py','gateway/fastapi/gpu_backend.py']:
    target=tests/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,target)
run(['docker','run','--rm','--network','none','--read-only','--user','0','--tmpfs','/tmp:size=32m',
    '-v',str(tests)+':/workspace:ro','--entrypoint','python','ai-gateway:mtls-20261030',
    '-m','unittest','discover','-s','/workspace/tests/operations','-p','test_gpu_backend.py','-v'])
print('MTLS_GATEWAY_BUILD_AND_RECOVERY_TESTS_PASSED')
