from pathlib import Path
import json,subprocess
for name in ('moara-directory-test','moara-ldap-alpha','moara-ldap-beta'):
 p=subprocess.run(['docker','inspect',name],capture_output=True,text=True)
 if p.returncode==0:
  obj=json.loads(p.stdout)[0]
  if obj['Config'].get('Labels',{}).get('moara.test')!='directory':raise RuntimeError('unowned fixture')
  subprocess.run(['docker','rm','-f',name],check=True,capture_output=True)
p=subprocess.run(['docker','network','inspect','moara-directory-qa'],capture_output=True,text=True)
if p.returncode==0:
 if json.loads(p.stdout)[0].get('Labels',{}).get('moara.test')!='directory':raise RuntimeError('unowned network')
 subprocess.run(['docker','network','rm','moara-directory-qa'],check=True,capture_output=True)
source=Path('/home/nutec/ai-server/moara/infrastructure/scripts/directory-staging.py').read_text()
source=source.replace("ROOT=Path(__file__).resolve().parents[3]","ROOT=Path('/home/nutec/ai-server')")
source=source.replace("(ROOT/'moara/tests/directory_acceptance.py')","Path('/home/nutec/moara-platform-20261026/moara/tests/directory_acceptance.py')")
exec(compile(source,'<directory-staging>','exec'),{'__name__':'__main__'})
