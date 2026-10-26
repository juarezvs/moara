#!/usr/bin/env bash
set -eu
cd /home/nutec/ai-server
printf '\nCOMPOSE_SERVICE_NAMES\n'
sh moara/infrastructure/scripts/compose.sh config --services
printf '\nROOTLESS_CAPABILITY_PROBE\n'
python3 - <<'PY'
import json,subprocess
from pathlib import Path
root=Path('/home/nutec/ai-server')
env=dict(x.split('=',1) for x in (root/'infrastructure/.env').read_text().splitlines() if '=' in x)
code="from pathlib import Path; p=Path('/source/secp_rbac_config.json'); f=p.open('rb'); f.read(1); f.close(); print('protected_file_readable_in_isolated_helper=true')"
r=subprocess.run(['docker','run','--rm','--pull=never','--network','none','--read-only','--cap-drop','ALL','--cap-add','DAC_READ_SEARCH','--security-opt','no-new-privileges:true','--memory','128m','--cpus','1','--mount',f'type=bind,src={root}/secrets,dst=/source,readonly',env['PYTHON_IMAGE'],'python','-c',code],capture_output=True,text=True)
print(r.stdout.strip());print('helper_exit='+str(r.returncode))
if r.returncode:raise SystemExit('helper unable to read protected configuration')
print('SOURCE_SYMLINKS')
for base in ['infrastructure','gateway','inference','agents','integrations','ia-studio','connectors','moara','docs','tests','secrets']:
 for p in (root/base).rglob('*'):
  if any(s in p.relative_to(root/base).parts for s in ['node_modules','.venv','wheels','wheels-before-otel','__pycache__','.git','dist']):continue
  if p.is_symlink(): print(p.relative_to(root))
print('UNIT_OVERRIDES')
for unit in ['ai-server.service','ai-backup.service']:
 r=subprocess.run(['systemctl','--user','show',unit,'-p','DropInPaths','-p','FragmentPath'],capture_output=True,text=True,check=True)
 print(r.stdout.strip())
PY
