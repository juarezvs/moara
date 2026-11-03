import pathlib,subprocess,shutil
root=pathlib.Path(__file__).resolve().parents[2];tag='moara-core:citations-v2-20261031';base='moara-core:pre-citations-20261031'
if subprocess.run(['docker','image','inspect',base],capture_output=True).returncode:
 current=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip();subprocess.run(['docker','tag',current,base],check=True)
folder=root/'tmp/citations-build';folder.mkdir(exist_ok=True)
shutil.copyfile(root/'moara/gateway/legal_answer.py',folder/'legal_answer.py')
shutil.copytree(root/'moara/web/dist/moara-web/browser',folder/'web',dirs_exist_ok=True)
(folder/'Dockerfile').write_text('FROM '+base+'\nCOPY legal_answer.py /app/moara/gateway/legal_answer.py\nCOPY web /app/web\n')
subprocess.run(['docker','build','--network','none','-t',tag,str(folder)],check=True)
subprocess.run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL','-v',str(root/'tmp/jurisprudence-build/tests')+':/tests:ro','--entrypoint','python',tag,'-m','unittest','discover','-s','/tests','-v'],check=True)
source=(root/'infrastructure/site-entry/stage_unified.py').read_text().replace('moara-core:unified-20261031',tag).replace('moara-unified-stage-','moara-citations-stage-')
exec(compile(source,'stage_citations','exec'),{'__file__':str(root/'infrastructure/site-entry/stage_unified.py')})
