"""Prepare candidate in isolated directory; never overwrite the production checkout."""
import json,os,shutil,subprocess,tarfile
from pathlib import Path
ROOT=Path('/home/nutec/ai-server');STAGE=Path('/home/nutec/moara-platform-20261026-r2')
def run(args,timeout=1800):
 p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
 if p.returncode:
  print(p.stdout[-10000:]);print(p.stderr[-10000:]);raise RuntimeError('candidate_build_failed')
 print(p.stdout[-1500:]);print(p.stderr[-3000:]);return p.stdout
STAGE.mkdir(mode=0o700,exist_ok=True)
with tarfile.open('/home/nutec/moara-platform-source.tar') as archive:archive.extractall(STAGE,filter='data')
shutil.copytree(ROOT/'moara/gateway/wheels',STAGE/'moara/gateway/wheels',dirs_exist_ok=True)
run(['docker','run','--rm','--label','moara.environment=platform-build','--memory','3g','--cpus','4','--pids-limit','256','--security-opt','no-new-privileges:true',
 '--mount',f'type=bind,source={STAGE}/moara/web,target=/work','-w','/work','node:24-bookworm-slim','sh','-c','npm ci --no-audit --no-fund && npm run build'],1800)
run(['docker','build','-t','moara-core:platform-20261026-r2','-f',str(STAGE/'moara/gateway/Dockerfile'),str(STAGE)],1800)
run(['docker','run','--rm','--network','none','--memory','1g','--cpus','2','--label','moara.environment=platform-test',
 '--mount',f'type=bind,source={STAGE}/moara/tests,target=/tests,readonly','moara-core:platform-20261026-r2','python','-m','unittest','discover','-s','/tests','-p','test_platform.py'],180)
print(json.dumps({'candidate_image':'moara-core:platform-20261026-r2','production_modified':False}))
