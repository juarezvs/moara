import subprocess
from pathlib import Path
source=Path('/home/nutec/moara-platform-20261026-r2/moara/tests/platform_deep_acceptance.py').read_bytes()
p=subprocess.run(['docker','exec','-i','moara-platform-qa-api','python','-'],input=source,capture_output=True,timeout=180)
print(p.stdout.decode());print(p.stderr.decode()[-6000:]);raise SystemExit(p.returncode)
