import subprocess
code="""from pathlib import Path
for p in Path('/app/backend/open_webui').rglob('*.py'):
 text=p.read_text()
 if 'internal/identity' in text:
  lines=text.splitlines();i=next(i for i,l in enumerate(lines) if 'internal/identity' in l);print(str(p));print('\\n'.join(lines[i:i+42]))
"""
p=subprocess.run(['docker','exec','-i','moara-directory-test','python','-'],input=code,text=True,capture_output=True);print(p.stdout)
