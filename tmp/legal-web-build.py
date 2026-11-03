import pathlib,shutil,subprocess
root=pathlib.Path('/home/nutec/ai-server');target=root/'tmp/legal-web-build'
target.mkdir(exist_ok=True)
for name in ['angular.json','package-lock.json','package.json','tsconfig.app.json','tsconfig.json']:
    shutil.copyfile(root/'moara/web'/name,target/name)
for name in ['src','public']:
    shutil.copytree(root/'moara/web'/name,target/name,dirs_exist_ok=True)
base=['docker','run','--rm','--network','ai-server_download','--memory','2g','--cpus','2','-v',str(target)+':/workspace','-w','/workspace','node:24-bookworm-slim']
subprocess.run(base+['npm','ci','--no-audit','--no-fund'],check=True)
subprocess.run(base+['npm','run','build'],check=True)
print('LEGAL_WEB_BUILD_PASSED',flush=True)
