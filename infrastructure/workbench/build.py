"""Build the new workspace UI on the exact preserved production core."""
import pathlib,subprocess,json,shutil
root=pathlib.Path(__file__).resolve().parents[2]
base='moara-core:pre-workbench-20261030';tag='moara-core:workbench-20261030'
if subprocess.run(['docker','image','inspect',base],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
    current=json.loads(subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1']))[0]['Image']
    subprocess.run(['docker','tag',current,base],check=True)
context=root/'tmp/workbench-build';context.mkdir(exist_ok=True)
(context/'Dockerfile').write_text('FROM '+base+'\nCOPY web /app/web\n')
shutil.copytree(root/'moara/web/dist/moara-web/browser',context/'web',dirs_exist_ok=True)
subprocess.run(['docker','build','--network','none','-t',tag,str(context)],check=True)
print('WORKBENCH_UI_IMAGE_BUILT_WITHOUT_BACKEND_OR_MODEL_CHANGE')
