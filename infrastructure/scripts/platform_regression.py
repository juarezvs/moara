import subprocess
from pathlib import Path
STAGE=Path('/home/nutec/moara-platform-20261026-r2')
file=STAGE/'Dockerfile.platform-tests';file.write_text('FROM moara-core:platform-20261026-r2\nUSER root\nRUN python -m pip install --no-cache-dir pytest==8.3.5\nUSER 10001:10001\n')
p=subprocess.run(['docker','build','-f',str(file),'-t','moara-platform-tests:20261026',str(STAGE)],capture_output=True,timeout=600)
if p.returncode:print(p.stderr.decode()[-2000:]);raise SystemExit(1)
p=subprocess.run(['docker','run','--rm','--network','none','--memory','1g','--cpus','2','--pids-limit','128','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL',
 '--mount',f'type=bind,source={STAGE}/moara,target=/suite/moara,readonly','--mount',f'type=bind,source=/home/nutec/moara-platform-20261026/connector-tests,target=/suite/connectors,readonly',
 '-e','PYTHONPATH=/suite','-w','/suite','moara-platform-tests:20261026','python','-m','pytest','-q','-p','no:cacheprovider','moara/tests','--ignore=moara/tests/browser_acceptance.py'],capture_output=True,text=True,timeout=240)
print(p.stdout[-12000:]);print(p.stderr[-2000:]);raise SystemExit(p.returncode)
