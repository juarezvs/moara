"""One-time source migration to Moara's institutional workspace composition."""
from pathlib import Path
import re
root=Path(__file__).resolve().parents[2]
p=root/'moara/web/src/app/workbench.html';s=p.read_text(encoding='utf8')
if 'workspace-overview' not in s:
 header=re.search(r'    <header class="work-nav">.*?</header>',s,re.S).group(0).strip()
 s=s.replace('    '+header+'\n','',1)
 header=re.sub(r'<button class="secondary history-toggle".*?</button>','',header,flags=re.S)
 header=re.sub(r'@if\(auth.can\(\'workspace.use\'\)\)\{<a class="work-fullscreen-link".*?</a>\}','',header,flags=re.S)
 header=header.replace('(click)="view.set(tab.id)"','(click)="selectArea(tab.id)"')
 s=s.replace('<aside class="work-history"','<aside id="moara-work-navigation" [cdkTrapFocus]="showHistory()" [cdkTrapFocusAutoCapture]="showHistory()" class="work-history"',1)
 s=re.sub(r'    <a class="work-brand".*?</a>', '<div class="work-space-label"><span>ESTAÇÃO DE TRABALHO</span><button type="button" class="work-close" (click)="closeHistory()" aria-label="Fechar áreas de trabalho">×</button></div>',s,count=1,flags=re.S)
 needle='<moara-work-icon name="plus"/>Novo trabalho</button>'
 s=s.replace(needle,needle+'\n    '+header,1)
 admin=re.search(r'    <nav class="work-central".*?</nav>',s,re.S).group(0)
 permissions="auth.can('users.manage')||auth.can('connectors.read')||auth.can('models.read')||auth.can('users.read')||auth.can('api_keys.manage')||auth.can('identity.draft')||auth.can('workspace.use')||auth.can('development.use')"
 s=s.replace(admin,"    @if("+permissions+"){<details class=\"work-administration\"><summary><moara-work-icon name=\"settings\"/>Administração e integrações</summary>"+admin.strip()+"</details>}",1)
 s=s.replace('<div class="nav-label">CENTRAL MOARA</div>','',1)
 s=s.replace('  <section class="work-main">','''  @if(showHistory()){<button type="button" class="work-menu-backdrop" (click)="closeHistory()" aria-label="Fechar áreas de trabalho"></button>}
  <section class="work-main">
    <div class="mobile-work-toolbar"><button type="button" class="secondary history-toggle" (click)="showHistory.set(!showHistory())" [attr.aria-expanded]="showHistory()" aria-controls="moara-work-navigation" aria-label="Mostrar áreas e histórico"><moara-work-icon name="menu"/><span>Áreas e histórico</span></button><span>{{areaTitle()}}</span></div>''',1)
 start=s.index('<div class="work-intro"><div class="intro-mark">')
 end=s.index('<div class="welcome-composer">',start)
 s=s[:start]+'''<div class="work-intro"><header class="workspace-overview"><div><span class="workspace-eyebrow">INTELIGÊNCIA INSTITUCIONAL</span><h1>Seu trabalho,<br>com mais clareza.</h1><p>Um espaço para reunir informações, desenvolver análises e transformar conhecimento em trabalho bem fundamentado.</p></div><button class="principal-control" type="button" (click)="toggleSettings()" [attr.aria-expanded]="settingsOpen()" aria-controls="work-settings" aria-label="Configurar assistente e modelo"><span class="assistant-dot" aria-hidden="true"></span><span>{{assistantId==='auto'?'Assistência automática':assistantName()}}</span><moara-work-icon name="settings"/></button></header><div class="welcome-layout"><div class="welcome-primary">
          '''+s[end:]
 s=s.replace('<div class="suggestions-label"><moara-work-icon name="sparkles"/>Para começar</div>','<div class="suggestions-label"><span>ATIVIDADES FREQUENTES</span><span>Escolha um ponto de partida</span></div>',1)
 marker='''          </div>
        </div>}
        <section'''
 replacement='''          </div>
          </div><aside class="welcome-aside" aria-label="Orientações do ambiente"><div class="welcome-guide"><span class="guide-kicker">UM BOM PONTO DE PARTIDA</span><h2>Do contexto<br>à próxima ação.</h2><ol><li><span>01</span><div><strong>Defina o objetivo</strong><p>Diga o que você precisa compreender ou produzir.</p></div></li><li><span>02</span><div><strong>Reúna o contexto</strong><p>Selecione os documentos e as referências do trabalho.</p></div></li><li><span>03</span><div><strong>Revise para decidir</strong><p>Confira fontes, premissas e resultados antes de utilizá-los.</p></div></li></ol></div><div class="welcome-resources"><span class="guide-kicker">APOIO AO TRABALHO</span><button type="button" (click)="view.set('referencias');referenceKind='metadados'"><moara-work-icon name="law"/><span><strong>Fontes e referências</strong><small>Normas, teses e evidências identificadas</small></span><moara-work-icon name="arrow"/></button><button type="button" (click)="view.set('historico')"><moara-work-icon name="history"/><span><strong>Continue de onde parou</strong><small>Seu histórico de trabalho na Moara</small></span><moara-work-icon name="arrow"/></button><p><moara-work-icon name="shield"/>IA local, com acesso orientado pelas permissões institucionais.</p></div></aside></div>
        </div>}
        <section'''
 assert marker in s;s=s.replace(marker,replacement,1)
 # Work mode is a separate document-format choice at the top of the composer.
 mode=re.search(r'<div class="mode-control"[^>]*>.*?</div>',s,re.S).group(0);s=s.replace(mode,'',1)
 target='<form class="work-composer chat-composer" (ngSubmit)="view.set(\'inicio\');send()">'
 assert target in s;s=s.replace(target,target+'<div class="composer-header"><span>{{workMode===\'draft\'?\'RASCUNHO DE DOCUMENTO\':workMode===\'plan\'?\'PLANO DE TRABALHO\':\'NOVA CONVERSA\'}}</span>'+mode+'</div>',1)
 s=s.replace('class="work-body" role="tabpanel"','class="work-body" tabindex="-1" role="tabpanel"',1)
 p.write_text(s,encoding='utf8')
p=root/'moara/web/src/app/chat.ts';s=p.read_text(encoding='utf8')
s=s.replace('OnDestroy }','OnDestroy,HostListener }').replace("import { FormsModule }", "import { A11yModule } from '@angular/cdk/a11y';\nimport { FormsModule }")
s=s.replace('imports:[FormsModule,','imports:[A11yModule,FormsModule,').replace("'./workbench-brand.css'","'./workbench-institutional.css'")
if 'areaTitle()' not in s:
 s=s.replace('  copiedMessage=signal', '''  areaTitle(){return this.workTabs.find(t=>t.id===this.view())?.name||'Área de trabalho';}
  selectArea(id:string){this.view.set(id);if(innerWidth<=980){this.showHistory.set(false);requestAnimationFrame(()=>document.querySelector<HTMLElement>('.work-body')?.focus());}}
  closeHistory(){this.showHistory.set(false);requestAnimationFrame(()=>document.querySelector<HTMLButtonElement>('.history-toggle')?.focus());}
  @HostListener('document:keydown.escape') closeWorkspaceMenu(){if(this.showHistory())this.closeHistory();}
  copiedMessage=signal''',1)
p.write_text(s,encoding='utf8')
p=root/'moara/web/src/app/shell.ts';s=p.read_text(encoding='utf8').replace("styleUrls:['./shell-header.css']","styleUrls:['./shell-header.css','./shell-institutional.css']");p.write_text(s,encoding='utf8')
