"""Compile the existing Angular app with its locked, previously used dependencies."""
import hashlib,pathlib,shutil,subprocess
root=pathlib.Path(__file__).resolve().parents[2];target=root/'tmp/moara2-web'
target.mkdir(exist_ok=True)
for name in ['angular.json','package-lock.json','package.json','tsconfig.app.json','tsconfig.json']:
    shutil.copyfile(root/'moara/web'/name,target/name)
for name in ['src','public']:shutil.copytree(root/'moara/web'/name,target/name,dirs_exist_ok=True)
base=['docker','run','--rm','--memory','2g','--cpus','2','-v',str(target)+':/workspace','-w','/workspace']
cached=root/'tmp/legal-web-build'
same_lock=(cached/'package-lock.json').is_file() and (cached/'package-lock.json').read_bytes()==(target/'package-lock.json').read_bytes()
if same_lock and (cached/'node_modules').is_dir():
    command=base+['--network','none','-v',str(cached/'node_modules')+':/workspace/node_modules:ro','node:24-bookworm-slim','npm','run','build']
else:
    subprocess.run(base+['--network','ai-server_download','node:24-bookworm-slim','npm','ci','--no-audit','--no-fund'],check=True)
    command=base+['--network','none','node:24-bookworm-slim','npm','run','build']
subprocess.run(command,check=True)
current=root/'moara/web/dist/moara-web/browser';backup=root/'backups/moara2-20261030/frontend-before'
if not backup.exists():shutil.copytree(current,backup)
shutil.copytree(target/'dist/moara-web/browser',current,dirs_exist_ok=True)
print('MOARA2_FRONTEND_BUILD_PASSED',flush=True)
