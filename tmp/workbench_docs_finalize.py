from pathlib import Path
import sys,json
root=Path('docs')
p=root/'MOARA_2_OPERATIONS.md';s=p.read_text(encoding='utf8');notice='\nA interface foi atualizada: a imagem ativa é `moara-core:workbench-20261030`, com `workbench-compose.yml` ao final do wrapper. Ver [ambiente de trabalho e reversão](MOARA_WORKBENCH_2026-10-30.md). A imagem foundation citada abaixo registra a entrega anterior da base.\n'
if 'MOARA_WORKBENCH_2026-10-30.md' not in s:s=s.replace('\n\n', '\n'+notice+'\n',1)
p.write_text(s,encoding='utf8')
p=root/'MOARA_2_USER_GUIDE.md';s=p.read_text(encoding='utf8');addition='\nO novo [ambiente de trabalho](MOARA_WORKBENCH_2026-10-30.md) reúne as áreas Início, Histórico, Documentos, Modelos, Referências e Acervo. Use a barra inferior para Conversar, Planejar ou preparar uma Minuta. No modo Planejar, abra o roteiro no editor, revise-o e selecione “Usar roteiro na minuta”; o envio seguinte prepara o rascunho.\n'
if 'MOARA_WORKBENCH_2026-10-30.md' not in s:p.write_text(s+addition,encoding='utf8')
links={'README.md':'\n[Ambiente de trabalho da Moara — interface e funcionalidades](docs/MOARA_WORKBENCH_2026-10-30.md).\n',
 'docs/PROJECT_STATUS.md':'\nAmbiente de trabalho publicado: [interface, funcionalidades e validação](MOARA_WORKBENCH_2026-10-30.md), inspirado nas referências visuais fornecidas. Backend, banco, residência GPU e controles jurídicos preservados.\n'}
for name,addition in links.items():
 p=Path(name);s=p.read_text(encoding='utf8')
 if 'MOARA_WORKBENCH_2026-10-30.md' not in s:p.write_text(s+addition,encoding='utf8')
sys.path.insert(0,'tmp')
from gpu_remote import source
script="""python3 - <<'PY'
from pathlib import Path
import json
root=Path('/home/nutec/ai-server')
for name,addition in json.loads(PAYLOAD).items():
 p=root/name;s=p.read_text()
 if 'MOARA_WORKBENCH_2026-10-30.md' not in s:p.write_text(s+addition)
print('WORKBENCH_DOCUMENTATION_LINKED')
PY
""".replace('PAYLOAD',repr(json.dumps(links)))
print(source(script))
