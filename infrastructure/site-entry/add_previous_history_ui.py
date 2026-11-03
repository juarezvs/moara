from pathlib import Path
p=Path(__file__).resolve().parents[2]/'moara/web/src/app/workbench.html';s=p.read_text(encoding='utf8')
if 'previous-history-panel' not in s:
 anchor="      @if(view()==='documentos')"
 block='''      @if(view()==='historico'){
        <section class="work-section previous-history-panel"><div class="section-heading"><div><span class="eyebrow">CONTINUIDADE NA MOARA</span><h2>Conversas anteriores</h2><p>Consulte seu histórico preservado e continue em uma cópia na interface atual.</p></div><button class="secondary" [disabled]="previousLoading()" (click)="loadPrevious()">Atualizar conversas anteriores</button></div>
        @if(previousLoading()){<p role="status">Consultando seu histórico…</p>}
        @if(previousSelected()){<div class="previous-actions"><button class="secondary" (click)="previousSelected.set(null)">Voltar à lista</button><a class="secondary" [href]="'/moara/api/v1/history/previous/'+previousSelected()!.id+'/export'" download>Exportar original</a><button class="primary" [disabled]="previousLoading()" (click)="resumePrevious()">Continuar em uma cópia</button></div><h3>{{previousSelected()!.title}}</h3><p class="notice-box">{{previousSelected()!.notice}}</p><div class="previous-messages">@for(m of previousSelected()!.messages;track $index){<article class="message" [class.user-message]="m.role==='user'"><strong>{{m.role==='user'?'Você':'Moara'}}</strong><div class="markdown" [innerHTML]="render(m.content)"></div></article>}</div>}
        @else if(previousLoaded()){@if(!previousAvailable()){<p class="notice-box">Esta conta não possui vínculo com o histórico anterior. Entre com a conta institucional que criou as conversas.</p>}<div class="resource-grid">@for(c of filteredPrevious();track c.id){<button class="resource-card" [disabled]="busy()||previousLoading()" (click)="openPrevious(c)"><moara-work-icon name="history"/><strong>{{c.title}}</strong><small>{{c.updated_at|date:'dd/MM/yyyy HH:mm'}}</small><span>Consultar conversa →</span></button>}@empty{<p class="empty-copy">Nenhuma conversa anterior encontrada nesta página.</p>}</div>@if(previousMore()){<button class="secondary" [disabled]="previousLoading()" (click)="loadPrevious(true)">Carregar mais conversas</button>}}
        @else{<button class="secondary" [disabled]="previousLoading()" (click)="loadPrevious()">Consultar minhas conversas anteriores</button>}
        </section>
      }
'''
 assert s.count(anchor)==1;s=s.replace(anchor,block+anchor)
 s=s.replace("@if(view()!=='editor'&&(messages().length||view()!=='inicio'))", "@if(view()!=='editor'&&!(view()==='historico'&&previousSelected())&&(messages().length||view()!=='inicio'))")
 p.write_text(s,encoding='utf8')
p=Path(__file__).resolve().parents[2]/'moara/web/src/app/workbench-brand.css'
with p.open('a',encoding='utf8') as f:f.write('''\n/* Context stays optional and never removes selected sources. */
.context-toggle.active{background:color-mix(in srgb,var(--primary) 12%,transparent);color:var(--primary);border-radius:8px}.work-composer-zone.context-expanded{position:static}.work-composer-zone>#work-context{max-width:850px;margin:20px auto 4px;text-align:center}.previous-actions{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0}.previous-history-panel h3{margin:20px 0}.previous-messages{margin-top:22px}.previous-messages .message{margin:15px 0}.previous-history-panel .notice-box{font-size:12px}.composer-toolbar .context-toggle{white-space:nowrap}.legacy-history.text-button{text-align:left;font-size:11px}.previous-history-panel .resource-grid{margin-top:20px}
@media(max-width:600px){.composer-toolbar{gap:7px;flex-wrap:wrap}.composer-toolbar .context-toggle{padding:7px}.work-composer-zone>#work-context{margin-top:15px}.previous-actions>a,.previous-actions>button{width:100%}}
''')
