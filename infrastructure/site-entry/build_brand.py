"""Restore original visual identity without changing the legal/inference backend."""
import pathlib,subprocess,shutil,json
root=pathlib.Path(__file__).resolve().parents[2]
base='moara-core:pre-brand-20261030';tag='moara-core:brand-20261030'
if subprocess.run(['docker','image','inspect',base],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
 current=json.loads(subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1']))[0]['Image']
 subprocess.run(['docker','tag',current,base],check=True)
folder=root/'tmp/moara-brand-build';folder.mkdir(exist_ok=True)
shutil.copytree(root/'moara/web/dist/moara-web/browser',folder/'web',dirs_exist_ok=True)
(folder/'Dockerfile').write_text('FROM '+base+'\nCOPY web /app/web\n')
subprocess.run(['docker','build','--network','none','-t',tag,str(folder)],check=True)
print('ORIGINAL_BRAND_FRONTEND_BUILT_ON_CURRENT_BACKEND')
