"""Run candidate only in a dedicated isolated PostgreSQL/Redis/API environment."""
import json,subprocess
from pathlib import Path
ROOT=Path('/home/nutec/ai-server');STAGE=Path('/home/nutec/moara-platform-20261026-r2')
source=(ROOT/'moara/infrastructure/scripts/staging.py').read_text()
source=source.replace("ROOT=Path(__file__).resolve().parents[3]","ROOT=Path('/home/nutec/ai-server')")
source=source.replace("secrets/moara-staging","secrets/moara-platform-qa").replace("moara-staging","moara-platform-qa")
source=source.replace('moara-core:1.0.0','moara-core:platform-20261026-r2')
source=source.replace("env=['MOARA_DB_HOST='+NAMES[0]],","env=['MOARA_DB_HOST='+NAMES[0],'MOARA_SANDBOX_READY=true'],")
source=source.replace("sql='''CREATE ROLE","sql='''CREATE EXTENSION IF NOT EXISTS vector;\nCREATE ROLE")
exec(compile(source,'<platform-staging>','exec'),{'__name__':'__main__','__file__':str(ROOT/'moara/infrastructure/scripts/staging.py')})
result=subprocess.run(['docker','exec','-i','moara-platform-qa-api','python','-'],input=(STAGE/'moara/tests/platform_acceptance.py').read_bytes(),capture_output=True,timeout=360)
print(result.stdout.decode());print(result.stderr.decode()[-12000:])
if result.returncode:raise SystemExit(result.returncode)
