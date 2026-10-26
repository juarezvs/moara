import {Component,inject,signal,OnDestroy} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {JsonPipe,DatePipe} from '@angular/common';
import {Api} from './api';
import {Auth} from './auth';
import {ErrorBox} from './ui';

type Resource={id:string;kind:string;title:string;version:number;group_id:string|null;body:Record<string,any>};
@Component({standalone:true,imports:[FormsModule,JsonPipe,DatePipe,ErrorBox],template:`
<section class="page-header"><div><h1>Espaço de trabalho</h1><p>Documentos, conhecimento e ferramentas da Moara.</p></div><button class="button" (click)="fresh()">Novo item</button></section>
<moara-error [error]="error()"/><p role="status" aria-live="polite">{{notice()}}</p>
<nav aria-label="Módulos do espaço de trabalho" class="platform-tabs">@for(tab of tabs;track tab.id){<button class="button" [attr.aria-pressed]="kind===tab.id" (click)="switchKind(tab.id)">{{tab.label}}</button>}</nav>
<div class="platform-grid"><section class="card"><h2>{{label()}}</h2>
@if(kind==='document'){<label>Adicionar documento (até 4 MiB)<input type="file" accept=".txt,.md,.csv,.pdf,.docx" (change)="upload($event)"></label><p>PDF digital, DOCX, texto ou CSV em UTF-8. OCR local para até 20 páginas digitalizadas por documento.</p>}
<ul class="platform-list">@for(r of resources();track r.id){<li><button class="text-button" (click)="select(r.id)">{{r.title}}</button><small>v{{r.version}} · {{r.group_id?'Compartilhado':'Privado'}}</small></li>}@empty{<li>Nenhum item neste módulo.</li>}</ul>
</section><section class="card"><h2>{{selected()? 'Editar item':'Novo item'}}</h2>
<label>Título<input [(ngModel)]="title" maxlength="200"></label>
<label>Compartilhamento<select [(ngModel)]="group"><option value="">Somente eu</option>@for(g of groups();track g.id){<option [value]="g.id">{{g.name}}</option>}</select></label>
@if(kind!=='document'){
<label>{{kind==='prompt'||kind==='template'?'Texto (use {{campo}} para variáveis)':'Descrição ou instruções'}}<textarea [(ngModel)]="description" rows="7" maxlength="40000"></textarea></label>
@if(kind==='template'){<label>Variáveis separadas por vírgula<input [(ngModel)]="variables"></label>}
@if(kind==='project'){<label>Linguagem<select [(ngModel)]="language"><option>python</option><option>fastapi</option><option>typescript</option><option>angular</option><option>react</option></select></label>}
@if(kind==='workflow'){<p>Fluxo de teste: registra uma notificação simulada, sem enviar mensagens.</p><label><input type="checkbox" [(ngModel)]="scheduleEnabled">Agendar execução</label><label>Intervalo em segundos (mínimo 300)<input type="number" [(ngModel)]="scheduleSeconds" min="300" max="2592000"></label>}
@if(kind==='assistant'||kind==='case'||kind==='dashboard'){
<fieldset><legend>Fontes autorizadas</legend>@for(d of documents();track d.id){<label><input type="checkbox" [checked]="sourceIds.includes(d.id)" (change)="toggleSource(d.id)">{{d.title}}</label>}</fieldset>}
@if(kind==='dashboard'){<label>Coluna de agrupamento<input [(ngModel)]="groupBy"></label><label>Operação<select [(ngModel)]="operation"><option value="count">Contagem</option><option value="sum">Soma</option><option value="average">Média</option></select></label><label>Coluna numérica<input [(ngModel)]="valueColumn"></label>}
}
<div class="platform-actions"><button class="button primary" [disabled]="busy()||!title.trim()||(!selected()&&kind==='document')" (click)="save()">Salvar versão</button>
@if(selected()){<button class="button" [disabled]="busy()" (click)="versions()">Histórico de versões</button><button class="button" [disabled]="busy()" (click)="archive()">Arquivar</button>}</div>
@if(selected()){
@if(kind==='document'){<button class="button" (click)="run('document.ingest')">Indexar para consulta</button><a class="button" [href]="'/moara/api/v1/platform/documents/'+selected()!.id+'/download'">Baixar original</a>}
@if(kind==='template'){@for(v of variableNames();track v){<label>{{v}}<textarea [(ngModel)]="fields[v]" rows="2"></textarea></label>}<button class="button" (click)="render()">Preencher e gerar DOCX</button>}
@if(kind==='assistant'||kind==='project'||kind==='case'){<label>Solicitação<textarea [(ngModel)]="query" rows="3" maxlength="2000"></textarea></label><button class="button" (click)="run(kind==='assistant'?'assistant.run':kind==='project'?'project.generate':'legal.draft')">{{kind==='case'?'Gerar rascunho para revisão':kind==='project'?'Propor plano e arquivos':'Consultar assistente'}}</button>}
@if(kind==='project'){
<label>Arquivo do projeto<select [(ngModel)]="fileName">@for(name of fileNames();track name){<option [value]="name">{{name}}</option>}</select></label>
<label>Conteúdo<textarea [(ngModel)]="projectFiles[fileName]" rows="10" spellcheck="false"></textarea></label><p>Salve uma versão antes de revisar e executar.</p>
@if(auth.can('development.execute')){<button class="button" (click)="reviewExecution()">Revisar arquivos para execução</button>}
@if(executionReview()){<p>A execução usará a versão {{executionReview().version}}, sem rede, por até 30 segundos. Confira os arquivos no resultado abaixo.</p><button class="button" [disabled]="!executionReview().execution_enabled" (click)="executeProject()">Aprovar e executar esta versão</button>}
}
@if(kind==='case'){<h3>Linha do tempo</h3><label>Data<input type="date" [(ngModel)]="eventDate"></label><label>Fato documentado<input [(ngModel)]="eventDescription" maxlength="2000"></label><label>Documento<select [(ngModel)]="eventDocument">@for(d of documents();track d.id){<option [value]="d.id">{{d.title}}</option>}</select></label><button class="button" (click)="addEvent()">Adicionar evento e salvar</button><pre class="platform-output">{{events|json}}</pre>}
@if(kind==='workflow'){<button class="button" (click)="run('workflow.run')">Executar teste</button>}
@if(kind==='dashboard'){<button class="button" (click)="analyze()">Calcular indicador</button>}
}
</section></div>
<section class="card"><h2>Consultar conhecimento</h2><label>Pergunta<input [(ngModel)]="question" maxlength="2000"></label><button class="button" [disabled]="busy()||question.length<2" (click)="ask()">Consultar fontes autorizadas</button></section>
@if(output()){<section class="card"><h2>Resultado</h2>@if(proposal()&&kind==='project'){<button class="button" (click)="acceptProposal()">Aceitar arquivos propostos nesta versão</button>}<pre class="platform-output">{{output()}}</pre></section>}
<section class="card"><div class="platform-actions"><h2>Execuções</h2><button class="button" (click)="loadJobs()">Atualizar</button></div>
<table><thead><tr><th>Operação</th><th>Estado</th><th>Data</th><th>Ações</th></tr></thead><tbody>@for(j of jobs();track j.id){<tr><td>{{operationLabel(j.kind)}}</td><td>{{statusLabel(j.status)}}</td><td>{{j.created_at|date:'dd/MM/yyyy HH:mm':'-0400'}}</td><td><button class="text-button" (click)="showJob(j.id)">Resultado</button>@if(j.status==='queued'||j.status==='running'){<button class="text-button" (click)="cancel(j.id)">Cancelar</button>}</td></tr>}</tbody></table></section>
`,styles:[`
.button{border:1px solid var(--input-border,#c8d4e8);border-radius:10px;padding:.65rem .9rem;background:var(--panel,#fff);color:var(--text,#163052);cursor:pointer}.button[aria-pressed=true]{background:var(--primary,#235bd8);border-color:var(--primary,#235bd8);color:white}.button:disabled{opacity:.5;cursor:default}.button:focus-visible{outline:3px solid #53b1fd;outline-offset:3px}.card{background:var(--panel,#fff);border:1px solid var(--border,#d9e3f3);border-radius:16px;box-shadow:0 8px 30px #12345606}label:has(input[type=checkbox]){display:flex;align-items:center;gap:.5rem}input[type=checkbox]{display:inline-block;width:auto}.platform-tabs,.platform-actions{display:flex;gap:.5rem;flex-wrap:wrap;margin:1rem 0}.platform-grid{display:grid;grid-template-columns:minmax(220px,1fr) 2fr;gap:1rem}.platform-list{list-style:none;padding:0}.platform-list li{display:flex;justify-content:space-between;gap:1rem;padding:.8rem 0;border-bottom:1px solid var(--border,#ddd)}label{display:block;margin:.8rem 0}input:not([type=checkbox]),select,textarea{display:block;width:100%;padding:.7rem;border:1px solid var(--border,#aaa);border-radius:8px;background:var(--surface,#fff);color:inherit}input[type=checkbox]{margin-right:.5rem}.card{padding:1.25rem;margin:1rem 0}.platform-output{white-space:pre-wrap;overflow-wrap:anywhere;max-height:650px;overflow:auto}table{width:100%;text-align:left}td,th{padding:.5rem}@media(max-width:850px){.platform-grid{grid-template-columns:1fr}}
`]})
export class PlatformPage implements OnDestroy{
 auth=inject(Auth);api=inject(Api);error=signal<unknown>(null);notice=signal('');busy=signal(false);
 resources=signal<Resource[]>([]);documents=signal<Resource[]>([]);groups=signal<any[]>([]);jobs=signal<any[]>([]);selected=signal<Resource|null>(null);output=signal('');
 tabs=[{id:'document',label:'Documentos'},{id:'prompt',label:'Prompts'},{id:'template',label:'Templates'},{id:'assistant',label:'Assistentes'},{id:'project',label:'MOARA DEV'},{id:'case',label:'Processos'},{id:'dashboard',label:'Analytics'},{id:'workflow',label:'MOARA FLOW'}];
 proposal=signal<any>(null);executionReview=signal<any>(null);projectFiles:Record<string,string>={};fileName='main.py';events:any[]=[];eventDate='';eventDescription='';eventDocument='';scheduleEnabled=false;scheduleSeconds=3600;
 kind='document';title='';group='';description='';variables='';language='python';sourceIds:string[]=[];fields:Record<string,string>={};query='';question='';groupBy='';operation='count';valueColumn='';timer:ReturnType<typeof setInterval>;
 constructor(){void this.load();this.timer=setInterval(()=>{void this.loadJobs();},8000);}
 ngOnDestroy(){clearInterval(this.timer);}
 label(){return this.tabs.find(t=>t.id===this.kind)?.label;}
 variableNames(){return this.variables.split(',').map(v=>v.trim()).filter(Boolean);}
 async action(fn:()=>Promise<void>){this.error.set(null);this.busy.set(true);try{await fn();}catch(e){this.error.set(e);}finally{this.busy.set(false);}}
 async load(){await this.action(async()=>{this.resources.set(await this.api.request<Resource[]>('/platform/resources?kind='+this.kind));this.documents.set(await this.api.request<Resource[]>('/platform/resources?kind=document'));this.groups.set(await this.api.request<any[]>('/platform/groups'));await this.loadJobs();});}
 async loadJobs(){try{this.jobs.set(await this.api.request<any[]>('/platform/runs'));}catch(e){this.error.set(e);}}
 switchKind(kind:string){this.kind=kind;this.fresh();void this.load();}
 fresh(){this.selected.set(null);this.proposal.set(null);this.executionReview.set(null);this.projectFiles={'main.py':''};this.fileName='main.py';this.events=[];this.scheduleEnabled=false;this.title='';this.group='';this.description='';this.variables='';this.sourceIds=[];this.fields={};this.output.set('');}
 async select(id:string){await this.action(async()=>{const r=await this.api.request<Resource>('/platform/resources/'+id);this.selected.set(r);this.title=r.title;this.group=r.group_id||'';this.description=r.body['text']||r.body['instructions']||r.body['description']||'';this.variables=(r.body['variables']||[]).join(', ');this.language=r.body['language']||'python';this.sourceIds=r.body['document_ids']|| (r.body['document_id']?[r.body['document_id']]:[]);this.groupBy=r.body['group_by']||'';this.operation=r.body['operation']||'count';this.valueColumn=r.body['value_column']||'';this.projectFiles={...(r.body['files']||{'main.py':''})};this.fileName=Object.keys(this.projectFiles)[0]||'main.py';this.events=r.body['events']||[];this.scheduleEnabled=r.body['schedule']?.enabled||false;this.scheduleSeconds=r.body['schedule']?.interval_seconds||3600;this.executionReview.set(null);});}
 toggleSource(id:string){this.sourceIds=this.sourceIds.includes(id)?this.sourceIds.filter(v=>v!==id):[...this.sourceIds,id];}
 body():Record<string,unknown>{
 const old=this.selected()?.body||{};
 if(this.kind==='document')return old;
 if(this.kind==='prompt'||this.kind==='template')return {text:this.description,variables:this.kind==='template'?this.variableNames():[]};
 if(this.kind==='assistant')return {...old,instructions:this.description,document_ids:this.sourceIds,tools:['knowledge.search']};
 if(this.kind==='project')return {...old,description:this.description,language:this.language,files:this.projectFiles};
 if(this.kind==='case')return {...old,description:this.description,document_ids:this.sourceIds,events:this.events};
 if(this.kind==='dashboard')return {description:this.description,document_id:this.sourceIds[0],group_by:this.groupBy,operation:this.operation,value_column:this.valueColumn||null,filters:{}};
 return {...old,description:this.description,schedule:{enabled:this.scheduleEnabled,interval_seconds:this.scheduleSeconds},steps:old['steps']||[{type:'notification.test',parameters:{message:this.description}}]};
 }
 async save(){await this.action(async()=>{const r=this.selected();const saved=await this.api.request<{id:string}>('/platform/resources'+(r?'/'+r.id:''),r?'PUT':'POST',{...(r?{version:r.version}:{kind:this.kind}),title:this.title,group_id:this.group||null,body:this.body()});this.notice.set('Versão salva.');await this.select(saved.id);this.resources.set(await this.api.request<Resource[]>('/platform/resources?kind='+this.kind));});}
 async archive(){await this.action(async()=>{const r=this.selected()!;await this.api.request('/platform/resources/'+r.id+'/archive','POST',{version:r.version});this.fresh();this.resources.set(await this.api.request<Resource[]>('/platform/resources?kind='+this.kind));this.notice.set('Item arquivado.');});}
 async versions(){await this.action(async()=>this.output.set(JSON.stringify(await this.api.request('/platform/resources/'+this.selected()!.id+'/versions'),null,2)));}
 async upload(event:Event){const input=event.target as HTMLInputElement;const file=input.files?.[0];if(!file)return;await this.action(async()=>{if(file.size>4194304)throw new Error('Limite de 4 MiB por documento.');const data=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=reject;reader.readAsDataURL(file);});const r=await this.api.request<{id:string}>('/platform/documents','POST',{filename:file.name,title:file.name,content_base64:data,group_id:this.group||null});this.resources.set(await this.api.request<Resource[]>('/platform/resources?kind=document'));this.documents.set(this.resources());await this.select(r.id);input.value='';this.notice.set('Documento armazenado. Clique em indexar para habilitar a consulta.');});}
 async run(operation:string){await this.action(async()=>{await this.api.request('/platform/runs','POST',{operation,resource_id:this.selected()!.id,input:operation==='document.ingest'||operation==='workflow.run'?{}:{[operation==='project.generate'?'instructions':'query']:this.query||'Resuma as fontes disponíveis.'},idempotency_key:crypto.randomUUID()});this.notice.set('Execução enfileirada. Acompanhe abaixo.');await this.loadJobs();});}
 async ask(){await this.action(async()=>{await this.api.request('/platform/runs','POST',{operation:'knowledge.answer',input:{query:this.question},idempotency_key:crypto.randomUUID()});this.notice.set('Consulta enfileirada.');await this.loadJobs();});}
 async showJob(id:string){await this.action(async()=>{const j=await this.api.request<any>('/platform/runs/'+id);this.output.set(JSON.stringify(j.result||{status:j.status,error:j.error_code},null,2));this.proposal.set(j.kind==='project.generate'&&j.result?{...j.result,run_id:j.id,resource_id:j.resource_id}:null);});}
 async cancel(id:string){await this.action(async()=>{await this.api.request('/platform/runs/'+id+'/cancel','POST');await this.loadJobs();});}
 download(data:Blob,name:string){const url=URL.createObjectURL(data);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 async render(){await this.action(async()=>{const r=await this.api.request<any>('/platform/templates/'+this.selected()!.id+'/render','POST',{version:this.selected()!.version,fields:this.fields});this.output.set(r.text);this.download(new Blob([Uint8Array.from(atob(r.docx_base64),(c:string)=>c.charCodeAt(0))],{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}),'moara-rascunho.docx');});}
 statusLabel(value:string){return ({queued:'Na fila',running:'Em execução',completed:'Concluída',failed:'Falhou',cancelled:'Cancelada'} as Record<string,string>)[value]||value;}
 operationLabel(value:string){return ({'workflow.run':'Fluxo','project.generate':'Proposta de projeto','project.execute':'Execução de projeto','document.ingest':'Indexação','knowledge.answer':'Consulta documental','legal.draft':'Minuta','assistant.run':'Assistente'} as Record<string,string>)[value]||value;}
 fileNames(){return Object.keys(this.projectFiles);}
 async addEvent(){if(!this.eventDate||!this.eventDescription||!this.eventDocument){this.error.set(new Error('Preencha data, fato e documento.'));return;}this.events=[...this.events,{date:this.eventDate,description:this.eventDescription,document_id:this.eventDocument}].sort((a,b)=>a.date.localeCompare(b.date));await this.save();}
 async acceptProposal(){await this.action(async()=>{const p=this.proposal();if(p.resource_id!==this.selected()?.id)throw new Error('Abra o projeto correspondente à proposta.');await this.api.request('/platform/projects/'+p.resource_id+'/accept','POST',{version:p.project_version,digest:p.digest,run_id:p.run_id});await this.select(p.resource_id);this.proposal.set(null);this.notice.set('Arquivos aceitos e versionados.');});}
 async reviewExecution(){await this.action(async()=>{const review=await this.api.request<any>('/platform/projects/'+this.selected()!.id+'/review');this.executionReview.set(review);this.output.set(JSON.stringify(review.files,null,2));});}
 async executeProject(){await this.action(async()=>{const review=this.executionReview();await this.api.request('/platform/projects/'+this.selected()!.id+'/execute','POST',{version:review.version,digest:review.digest});this.executionReview.set(null);this.notice.set('Execução aprovada para a versão revisada.');await this.loadJobs();});}
 async analyze(){await this.action(async()=>{const r=await this.api.request<any>('/platform/analytics/query','POST',{document_id:this.sourceIds[0],group_by:this.groupBy,operation:this.operation,value_column:this.valueColumn||null,filters:{}});this.output.set(JSON.stringify(r,null,2));this.download(new Blob([r.csv],{type:'text/csv;charset=utf-8'}),'moara-indicador.csv');});}
}
