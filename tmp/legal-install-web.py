import pathlib,shutil,subprocess
root=pathlib.Path('/home/nutec/ai-server')
current=root/'moara/web/dist/moara-web/browser'
backup=root/'backups/legal-20261030/original-web'
if not backup.exists():shutil.copytree(current,backup)
new=root/'tmp/legal-web-build/dist/moara-web/browser'
if not (new/'index.html').is_file():raise RuntimeError('frontend_build_required')
shutil.copytree(new,current,dirs_exist_ok=True)
subprocess.run(['python3',str(root/'tmp/legal-build.py')],check=True)
subprocess.run(['sh',str(root/'moara/infrastructure/scripts/compose.sh'),'up','-d','--no-deps','--no-build','--pull','never','--wait','--wait-timeout','120','moara-gateway','moara-legal-mcp'],check=True)
print('LEGAL_FRONTEND_INSTALLED',flush=True)
