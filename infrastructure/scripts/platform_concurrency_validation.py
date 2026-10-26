import subprocess
from pathlib import Path
p=subprocess.run(['docker','exec','-i','moara-platform-qa-api','python','-'],input=Path('/home/nutec/moara-platform-20261026/moara/tests/platform_concurrency.py').read_bytes(),capture_output=True,timeout=120)
print(p.stdout.decode());print(p.stderr.decode()[-3000:]);raise SystemExit(p.returncode)
