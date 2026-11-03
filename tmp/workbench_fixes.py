from pathlib import Path
p=Path('moara/web/src/app/workbench.html');s=p.read_text(encoding='utf8')
s=s.replace('Assistente<select [(ngModel)]="assistantId"','Assistente<select aria-label="Assistente" [(ngModel)]="assistantId"')
s=s.replace('Modelo de execução<select name="profile"','Modelo de execução<select aria-label="Modelo de execução" name="profile"')
s=s.replace('Redação<select [(ngModel)]="writingLength"','Redação<select aria-label="Redação" [(ngModel)]="writingLength"')
p.write_text(s,encoding='utf8')
p=Path('moara/web/src/app/workbench.css');s=p.read_text();s+='\n.work-nav{position:relative}.work-nav nav{margin-inline:auto}.work-fullscreen-link{position:absolute;right:20px;margin-left:0}\n';p.write_text(s)
