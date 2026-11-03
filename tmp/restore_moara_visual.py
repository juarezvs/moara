from pathlib import Path
p=Path('moara/web/src/app/workbench.html');s=p.read_text(encoding='utf8')
needle='    <label class="history-search">'
central='''    <nav class="work-central" aria-label="Central Moara"><div class="nav-label">CENTRAL MOARA</div>
      @if(auth.can('users.manage')){<a href="/static/moara/directories.html"><moara-work-icon name="building"/><span>Órgãos e diretórios</span></a>}
      @if(auth.can('connectors.read')){<a routerLink="/fontes"><moara-work-icon name="database"/><span>Fontes de dados</span></a>}
      @if(auth.can('models.read')){<a routerLink="/modelos"><moara-work-icon name="server"/><span>Modelos e inferência</span></a>}
      @if(auth.can('users.read')||auth.can('api_keys.manage')){<a routerLink="/acessos"><moara-work-icon name="key"/><span>Contas e integrações</span></a>}
      @if(auth.can('identity.draft')){<a routerLink="/identidade"><moara-work-icon name="shield"/><span>Identidade institucional</span></a>}
      @if(auth.can('workspace.use')){<a routerLink="/espaco"><moara-work-icon name="folder"/><span>Espaço de trabalho</span></a>}
    </nav>
'''
assert needle in s;s=s.replace(needle,central+needle,1)
needle='    <a class="legacy-history" href="/?interface=anterior">Abrir histórico anterior ↗</a>'
s=s.replace(needle,needle+'''<div class="work-user"><span class="work-avatar">{{auth.user()?.name?.slice(0,1)}}</span><span><strong>{{auth.user()?.name}}</strong><small><i></i> Ambiente institucional</small></span><moara-work-icon name="shield"/></div>''',1)
start=s.index('@if(!messages().length){<div class="work-intro">')
end=s.index('          <div class="context-card">',start)
s=s[:start]+'''@if(!messages().length){<div class="work-intro"><div class="intro-mark"><img src="brand/mark.svg" alt=""><h1>Moara<span>Inteligência a serviço da Justiça.</span></h1></div><button class="principal-control" type="button" (click)="toggleSettings()" [attr.aria-expanded]="settingsOpen()" aria-controls="work-settings" aria-label="Configurar assistente e modelo"><moara-work-icon name="sparkles"/><span>{{assistantId==='auto'?'Moara AI · Automático':assistantName()}}</span><span aria-hidden="true">⌄</span></button><h2 class="welcome-question">Como posso ajudar você <span>hoje?</span></h2><p class="welcome-description">Sua IA local, segura e privada.<br>Transforme informações em trabalho bem fundamentado.</p>
'''+s[end:]
start=s.index('          <div class="work-starters">');end=s.index('</div>',start)+len('</div>')
s=s[:start]+'''          <div class="suggestions-label"><moara-work-icon name="sparkles"/>Para começar</div><div class="work-starters">
            <button type="button" (click)="startTask('Resuma os documentos selecionados e cite as fontes.','documental','chat');view.set('documentos')"><span class="starter-icon"><moara-work-icon name="document"/></span><span><strong>Analisar documentos</strong><small>Arquivos, trechos e referências rastreáveis</small></span><moara-work-icon name="arrow"/></button>
            <button type="button" (click)="view.set('referencias');referenceKind='normas'"><span class="starter-icon"><moara-work-icon name="law"/></span><span><strong>Conferir legislação</strong><small>Fontes oficiais e a data relevante do caso</small></span><moara-work-icon name="arrow"/></button>
            <button type="button" (click)="startTask('Prepare uma estrutura de termo de referência para aquisição de cadeiras, com campos pendentes.','administrativa','draft')"><span class="starter-icon"><moara-work-icon name="edit"/></span><span><strong>Preparar uma minuta</strong><small>Uma estrutura para sua revisão</small></span><moara-work-icon name="arrow"/></button>
            <button type="button" (click)="startTask('Proponha um roteiro para organizar a cronologia de autos judiciais, sem inventar fatos.','gabinete','plan')"><span class="starter-icon"><moara-work-icon name="briefcase"/></span><span><strong>Organizar o gabinete</strong><small>Cronologia, pendências e roteiro de trabalho</small></span><moara-work-icon name="arrow"/></button>
            <button type="button" (click)="startTask('Ajude a planejar uma solução para organizar arquivos institucionais. Identifique os requisitos e proponha código para revisão, sem executar operações sobre arquivos reais.','desenvolvedora','plan')"><span class="starter-icon"><moara-work-icon name="code"/></span><span><strong>Desenvolver uma solução</strong><small>Código e automações para revisão</small></span><moara-work-icon name="arrow"/></button>
            <button type="button" (click)="startTask('Ajude a planejar uma consulta a dados institucionais autorizados. Identifique fonte, campos e filtros necessários, sem inferir números.','dados','plan')"><span class="starter-icon"><moara-work-icon name="database"/></span><span><strong>Explorar dados institucionais</strong><small>Fontes, campos e filtros autorizados</small></span><moara-work-icon name="arrow"/></button>
          </div>'''+s[end:]
s=s.replace('(click)="settingsOpen.set(!settingsOpen())"','(click)="toggleSettings()"')
s=s.replace('<section class="work-settings"','<section id="work-settings" class="work-settings"',1)
p.write_text(s,encoding='utf8')
p=Path('moara/web/src/app/chat.ts');s=p.read_text(encoding='utf8').replace("'./workbench-progress.css']","'./workbench-progress.css','./workbench-brand.css']")
needle='  startTask(text:string,'
assert needle in s
s=s.replace(needle,"  toggleSettings(){this.settingsOpen.set(!this.settingsOpen());if(this.settingsOpen())requestAnimationFrame(()=>document.getElementById('work-settings')?.scrollIntoView({block:'nearest'}));}\n"+needle,1)
p.write_text(s,encoding='utf8')
