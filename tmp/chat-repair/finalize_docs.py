from pathlib import Path
import sys,json
links={'README.md':'\n[Correções de conversa e contexto de anexos](docs/MOARA_CHAT_REPAIRS_2026-10-30.md).\n',
 'docs/PROJECT_STATUS.md':'\nCorreção publicada: [perguntas sobre capacidades, continuação por data e orçamento de anexos](MOARA_CHAT_REPAIRS_2026-10-30.md). PDF fornecido validado pelo chat original; manifesto e residência GPU preservados.\n'}
for name,text in links.items():
 p=Path(name);value=p.read_text(encoding='utf8')
 if 'MOARA_CHAT_REPAIRS_2026-10-30.md' not in value:p.write_text(value+text,encoding='utf8')
p=Path('docs/MOARA_2_OPERATIONS.md');s=p.read_text(encoding='utf8')
s=s.replace('a imagem ativa é `moara-core:workbench-20261030`, com `workbench-compose.yml` ao final do wrapper.','a imagem ativa é `moara-core:chat-intent-20261030`, com `chat-intent-compose.yml` ao final do wrapper. Ela preserva o ambiente de trabalho e inclui as [correções de conversa/anexos](MOARA_CHAT_REPAIRS_2026-10-30.md).')
p.write_text(s,encoding='utf8')
sys.path.insert(0,'tmp')
from gpu_remote import source
script="""python3 - <<'PY'
from pathlib import Path
import json
root=Path('/home/nutec/ai-server')
for name,text in json.loads(PAYLOAD).items():
 p=root/name;value=p.read_text()
 if 'MOARA_CHAT_REPAIRS_2026-10-30.md' not in value:p.write_text(value+text)
print('CHAT_REPAIR_DOCUMENTATION_LINKED')
PY
""".replace('PAYLOAD',repr(json.dumps(links)))
print(source(script))
