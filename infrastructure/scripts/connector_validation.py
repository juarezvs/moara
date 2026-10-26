import json,shutil,subprocess
from pathlib import Path
ROOT=Path('/home/nutec/ai-server');STAGE=Path('/home/nutec/moara-platform-20261026')
suite=STAGE/'connector-tests';suite.mkdir(exist_ok=True)
for folder in ('common','hub','worker','secp_rbac'):
 shutil.copytree(ROOT/'connectors'/folder,suite/folder,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','node_modules'))
shutil.copytree(ROOT/'connectors/tests',suite/'tests',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
dockerfile=STAGE/'Dockerfile.connector-tests'
dockerfile.write_text('FROM node:24-bookworm-slim AS node\nFROM ai-connector-hub:1.0.0\nUSER root\nCOPY --from=node /usr/local/bin/node /usr/local/bin/node\nRUN python -m pip install --no-cache-dir pytest==8.3.5\nUSER 10001:10001\n')
p=subprocess.run(['docker','build','-f',str(dockerfile),'-t','moara-connector-tests:20261026',str(STAGE)],capture_output=True,timeout=600)
if p.returncode:print(p.stderr.decode()[-3000:]);raise SystemExit(1)
args=['docker','run','--rm','--network','none','--memory','1g','--cpus','2','--pids-limit','128','--read-only','--tmpfs','/tmp:size=64m',
 '--cap-drop','ALL','--security-opt','no-new-privileges:true','--mount',f'type=bind,source={suite},target=/suite,readonly','-w','/suite',
 '--entrypoint','python','moara-connector-tests:20261026','-m','pytest','-q','-p','no:cacheprovider','tests/test_policy.py','tests/test_secp_rbac.py','tests/test_secp_integration.py']
p=subprocess.run(args,capture_output=True,text=True,timeout=180)
print(p.stdout[-10000:]);print(p.stderr[-2000:]);raise SystemExit(p.returncode)
