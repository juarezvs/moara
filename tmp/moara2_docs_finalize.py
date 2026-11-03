from pathlib import Path
for name in ['docs/MOARA_2_IMPLEMENTATION_2026-10-30.md','docs/MOARA_2_OPERATIONS.md']:
    p=Path(name);s=p.read_text(encoding='utf8').replace('42 testes','43 testes');p.write_text(s,encoding='utf8')
p=Path('docs/MOARA_2_DIAGNOSTIC_2026-10-30.md');s=p.read_text(encoding='utf8').replace('O catálogo de oito agentes técnicos','O catálogo de agentes técnicos preexistentes');p.write_text(s,encoding='utf8')
links={
    'README.md':'\nMoara 2.0: [implantação, validações e limites](docs/MOARA_2_IMPLEMENTATION_2026-10-30.md).\n',
    'docs/PROJECT_STATUS.md':'\nAtualização de 30/10/2026: [Moara 2.0 — implantação e validação](MOARA_2_IMPLEMENTATION_2026-10-30.md). Base institucional e inferência mTLS publicadas; PJe/SEI pendentes de mecanismos oficiais e conclusões jurídicas automáticas suspensas quando a verificação não é conclusiva.\n'}
for name,addition in links.items():
    p=Path(name);s=p.read_text(encoding='utf8')
    if 'MOARA_2_IMPLEMENTATION_2026-10-30.md' not in s:p.write_text(s+addition,encoding='utf8')
# The source repository is complete; append only these links remotely.
import sys,json
sys.path.insert(0,'tmp')
from gpu_remote import source
script="""python3 - <<'PY'
from pathlib import Path
import json
root=Path('/home/nutec/ai-server')
for name,addition in json.loads(PAYLOAD).items():
 p=root/name;s=p.read_text()
 if 'MOARA_2_IMPLEMENTATION_2026-10-30.md' not in s:p.write_text(s+addition)
print('DOCUMENTATION_LINKS_APPENDED')
PY
""".replace('PAYLOAD',repr(json.dumps(links)))
print(source(script))
