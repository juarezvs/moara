"""Deterministic UTF-8 edits to the current portal, never to stored user content."""
from pathlib import Path
root=Path(__file__).resolve().parents[2]
p=root/'moara/web/src/app/workbench.html';s=p.read_text(encoding='utf8')
if 'toggleContext()' not in s:
 start=s.index('          <div class="context-card">');end=s.index('          <div class="suggestions-label">',start)
 card=s[start:end].strip().replace('<div class="context-card">','<div id="work-context" class="context-card" role="region" aria-labelledby="work-context-title">',1).replace('<strong>Contexto do trabalho</strong>','<strong id="work-context-title">Contexto de trabalho</strong>')
 s=s[:start]+s[end:]
 anchor='<span class="context-meter"'
 button='<button type="button" class="composer-settings context-toggle" (click)="toggleContext()" [class.active]="contextOpen()" [attr.aria-expanded]="contextOpen()" aria-controls="work-context"><moara-work-icon name="context"/>Contexto</button>'
 assert s.count(anchor)==1;s=s.replace(anchor,button+anchor,1)
 anchor='      </footer>\n    </ng-template>';assert s.count(anchor)==1
 s=s.replace(anchor,'        @if(contextOpen()){'+card+'}\n'+anchor,1)
 s=s.replace('<footer class="work-composer-zone">','<footer class="work-composer-zone" [class.context-expanded]="contextOpen()">')
 # Previous conversations now live inside this interface.
 s=s.replace('<a class="legacy-history" href="/?interface=anterior">Abrir histórico anterior ↗</a>','<button class="legacy-history text-button" (click)="view.set(\'historico\');loadPrevious()">Conversas anteriores →</button>')
 s=s.replace('<a href="/?interface=anterior" class="secondary">Histórico anterior ↗</a>','<button type="button" class="secondary" (click)="loadPrevious()">Conversas anteriores</button>')
 p.write_text(s,encoding='utf8')
p=root/'moara/web/src/app/shell.ts';s=p.read_text(encoding='utf8')
s=s.replace("import { AccessibilitySettings } from './accessibility';","import { AccessibilitySettings } from './accessibility';\nimport {WorkbenchIcon} from './workbench-icon';") if "from './workbench-icon'" not in s else s
s=s.replace('ErrorBox,AccessibilitySettings],template:','ErrorBox,AccessibilitySettings,WorkbenchIcon],styleUrls:[\'./shell-header.css\'],template:')
s=s.replace('<a href="/?interface=anterior">Chat institucional ↗</a>','')
start=s.index('<header class="topbar">');end=s.index('</header>',start)+len('</header>')
s=s[:start]+'''<header class="topbar moara-site-header"><div class="header-leading"><button class="icon-button mobile-menu" (click)="openMenu()" aria-label="Abrir navegação"><moara-work-icon name="menu"/></button><a class="header-brand" routerLink="/chat" aria-label="Moara — início"><img src="brand/mark.svg" alt=""><span><strong>Moara</strong><small>Justiça Federal do Amazonas</small></span></a></div><div class="header-section"><span>{{headerTitle()}}</span><small>Inteligência a serviço da Justiça.</small></div><div class="top-actions"><span class="header-private"><i></i><span>IA local e privada</span></span><moara-accessibility/><button class="icon-button theme-control" (click)="auth.toggleTheme()" [attr.aria-label]="auth.theme()==='light'?'Ativar tema escuro':'Ativar tema claro'"><moara-work-icon name="sun"/></button></div></header>'''+s[end:]
anchor='  async logout()'
if 'headerTitle(){' not in s:s=s.replace(anchor,"  headerTitle(){const url=this.router.url.split('?')[0];return url.startsWith('/chat')?'Ambiente de trabalho':url.startsWith('/desenvolvimento')?'Desenvolvimento':url.startsWith('/fontes')?'Fontes de dados':url.startsWith('/modelos')?'Modelos e inferência':url.startsWith('/espaco')?'Espaço de trabalho':'Plataforma institucional';}\n"+anchor)
p.write_text(s,encoding='utf8')
