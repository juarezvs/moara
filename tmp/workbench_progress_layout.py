from pathlib import Path
p=Path('moara/web/src/app/workbench.html');s=p.read_text(encoding='utf8')
s=s.replace('<header class="work-nav">','<header class="work-nav"><div class="work-rail-tools">',1)
s=s.replace('role="tablist"','role="tablist" aria-orientation="vertical"',1)
s=s.replace('</a></header>','</a></div></header>',1)
s=s.replace('<section class="chat-panel work-conversation"','<section [attr.aria-busy]="busy()" class="chat-panel work-conversation"',1)
old='@if(busy()){<div class="stream-status" role="status"><span class="spinner"></span>{{received()?\'Recebendo resposta…\':\'Processando solicitação…\'}}<button class="secondary" (click)="stop()">Interromper</button></div>}'
new='@if(busy()){<div class="stream-status moara-processing" role="status" aria-live="polite" aria-atomic="true"><span class="processing-mark" aria-hidden="true"><img src="brand/mark.svg" alt=""></span><span class="processing-copy"><strong>Moara</strong><span>{{processing()}}</span></span><button type="button" class="text-button" (click)="stop()">Interromper</button></div>}'
assert old in s;s=s.replace(old,new)
p.write_text(s,encoding='utf8')
