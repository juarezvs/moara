from pathlib import Path
p=Path('moara/web/src/app/chat.ts');s=p.read_text(encoding='utf8');s=s.replace("if(files.length>16){this.error.set(new Error('Envie até 16 arquivos por vez.'));return;}","if(files.length>16||files.length+this.documentIds.length>16){this.error.set(new Error('O contexto aceita até 16 documentos. Remova seleções antes de acrescentar estes arquivos.'));return;}")
p.write_text(s,encoding='utf8')
p=Path('moara/web/src/app/workbench.css');s=p.read_text();s+='\n.mode-control button{min-height:30px}@media(max-width:600px){.mode-control button{font-size:10px;min-height:32px}}\n';p.write_text(s)
