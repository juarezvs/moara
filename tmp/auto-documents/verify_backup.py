from pathlib import Path
import json,subprocess
root=Path('/home/nutec/ai-server')
p=root/'moara/infrastructure/scripts/preservation.py';s=p.read_text()
old="name,'pg_isready','-U','postgres','-d','ai'"
new="name,'pg_isready','-h','127.0.0.1','-U','postgres','-d','ai'"
assert s.count(old)==1;p.write_text(s.replace(old,new))
manifest=json.loads((root/'docs/runtime/moara-preservation-latest.json').read_text())
subprocess.run(['python3',str(p),'verify',str(root/'backups'/manifest['file'])],check=True)
