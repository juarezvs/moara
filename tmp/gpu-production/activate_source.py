import json,subprocess,pathlib,os
ROOT=pathlib.Path('/home/nutec/ai-server');WORK=ROOT/'tmp/gpu-production';os.umask(0o077)
code=(WORK/'activate_catalog.py').read_text()
r=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-'],input=code,text=True,capture_output=True,timeout=120)
for line in r.stdout.splitlines():
 if line.startswith('CATALOG_BACKUP='):
  p=ROOT/'backups/gpu-production-catalog-20261029.json'
  if not p.exists():p.write_text(line.split('=',1)[1]);p.chmod(0o600)
 else:print(line,flush=True)
if r.returncode:
 print(r.stderr[-1500:]);raise SystemExit(r.returncode)
cmd=['sh',str(ROOT/'moara/infrastructure/scripts/compose.sh')]
subprocess.run(cmd+['config','--quiet'],check=True)
subprocess.run(cmd+['up','-d','--no-deps','--no-build','--pull','never','--wait','--wait-timeout','180','gateway','moara-gateway'],check=True)
print('PRODUCTION_GATEWAYS_DEPLOYED',flush=True)
