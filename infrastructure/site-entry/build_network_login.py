import pathlib,subprocess,shutil
root=pathlib.Path(__file__).resolve().parents[2]
base='moara-core:pre-network-login-20261031'
if subprocess.run(['docker','image','inspect',base],capture_output=True).returncode:
 current=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
 subprocess.run(['docker','tag',current,base],check=True)
folder=root/'tmp/network-login-build';folder.mkdir(exist_ok=True)
shutil.copytree(root/'moara/web/dist/moara-web/browser',folder/'web',dirs_exist_ok=True)
(folder/'Dockerfile').write_text('FROM '+base+'\nCOPY web /app/web\n')
subprocess.run(['docker','build','--network','none','-t','moara-core:network-login-20261031',str(folder)],check=True)
source=(root/'infrastructure/site-entry/stage_unified.py').read_text().replace("image='moara-core:unified-20261031'","image='moara-core:network-login-20261031'")
exec(compile(source,'stage_network_login','exec'),{'__file__':str(root/'infrastructure/site-entry/stage_unified.py')})
