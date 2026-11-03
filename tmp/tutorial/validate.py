import re,zipfile
from pathlib import Path
r=Path('output/tutorial-moara');s=(r/'tutorial-moara.html').read_text(encoding='utf-8')
paths=[x for x in re.findall(r'(?:href|src)="([^"]+)"',s) if not x.startswith(('http','#'))]
assert all((r/x).is_file() for x in paths)
z=zipfile.ZipFile('output/tutorial-moara-completo.zip');assert z.testzip() is None
print('HTML references and ZIP verified.')
print('ZIP files:',len(z.namelist()))
print('PDF bytes:',Path('output/pdf/tutorial-moara.pdf').stat().st_size)
