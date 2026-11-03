import {Component,inject,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {DatePipe} from '@angular/common';
import {Api} from './api';
import {Auth} from './auth';
import {ErrorBox} from './ui';
import {OfficialAssistant} from './assistant-picker';
interface Version {revision:number;created_at:string;author:string;definition:{enabled:boolean;instructions:string;tools:string[]};sha256:string;}
interface Integration {id:string;name:string;portal:string;state:string;read_only:boolean;}
@Component({standalone:true,imports:[FormsModule,DatePipe,ErrorBox],template:`
<section class="page-header"><div><span class="eyebrow">GOVERNANÇA DA MOARA</span><h1>Assistentes institucionais</h1><p>Instruções versionadas, competências e ferramentas autorizadas.</p></div></section>
<moara-error [error]="error()"/><p role="status" aria-live="polite">{{notice()}}</p>
<p>As políticas institucionais centrais e as permissões de cada usuário aplicam-se a todos os assistentes.</p>
<div class="platform-grid"><section class="card"><h2>Catálogo oficial</h2><ul class="platform-list">@for(a of catalog();track a.id){<li><button type="button" class="text-button" (click)="select(a)">{{a.name}}</button><small>Versão {{a.revision}} · {{a.enabled?'Ativa':'Desativada'}}</small></li>}</ul></section>
@if(selected()){<section class="card"><h2>{{selected()!.name}}</h2><p>{{selected()!.mission}}</p><label><input type="checkbox" [(ngModel)]="enabled">Assistente ativa</label><label>Instruções da especialidade<textarea [(ngModel)]="instructions" rows="12" maxlength="6000"></textarea></label><fieldset><legend>Ferramentas permitidas</legend>@for(tool of selected()!.tool_catalog||[];track tool){<label class="check-label"><input type="checkbox" [checked]="tools.includes(tool)" (change)="toggleTool(tool)">{{toolLabel(tool)}}</label>}</fieldset><p class="small muted">Modelo principal compartilhado · Política {{selected()!.policy_version}}</p><button type="button" class="button primary" [disabled]="busy()||instructions.length<20" (click)="save()">Publicar nova versão</button><h3>Histórico de instruções</h3><ul>@for(v of versions();track v.revision){<li>Versão {{v.revision}} · {{v.created_at|date:'dd/MM/yyyy HH:mm'}} <button type="button" class="text-button" (click)="useVersion(v)">Carregar no formulário</button></li>}</ul></section>}</div>
@if(integrations().length){<section class="card section-gap"><h2>Integrações oficiais preparadas</h2><p>As consultas permanecem desabilitadas até a homologação dos mecanismos oficiais pelo tribunal. Escrita, assinatura, tramitação e publicação não estão habilitadas.</p>@for(i of integrations();track i.id){<article><h3>{{i.name}}</h3><a [href]="i.portal" rel="noreferrer" target="_blank">Portal institucional ↗</a><p>Aguardando mecanismo oficial de integração · Contrato somente de leitura</p></article>}</section>}
`})
export class AssistantsAdmin {
  api=inject(Api);auth=inject(Auth);catalog=signal<OfficialAssistant[]>([]);selected=signal<OfficialAssistant|null>(null);versions=signal<Version[]>([]);integrations=signal<Integration[]>([]);error=signal<unknown>(null);notice=signal('');busy=signal(false);enabled=true;instructions='';tools:string[]=[];
  constructor(){void this.load();}
  async load(){try{const values=await this.api.request<OfficialAssistant[]>('/assistants/admin/catalog');this.catalog.set(values);const chosen=values.find(v=>v.id===this.selected()?.id)||values[0];if(chosen)await this.select(chosen);if(this.auth.can('connectors.read'))this.integrations.set(await this.api.request<Integration[]>('/official-integrations'));}catch(e){this.error.set(e);}}
  async select(value:OfficialAssistant){this.selected.set(value);this.enabled=value.enabled;this.instructions=value.instructions||'';this.tools=[...value.tools];try{this.versions.set(await this.api.request<Version[]>('/assistants/admin/'+value.id+'/versions'));}catch(e){this.error.set(e);}}
  toggleTool(tool:string){this.tools=this.tools.includes(tool)?this.tools.filter(v=>v!==tool):[...this.tools,tool];}
  toolLabel(tool:string){return ({'normas.read':'Pesquisa normativa oficial','jurisprudencia.read':'Referências jurisprudenciais oficiais','documents.read':'Leitura de documentos autorizados','documents.search':'Pesquisa em documentos autorizados','documents.export':'Exportação documental autorizada','data.read':'Consultas de dados somente leitura','development.propose':'Propostas de código e testes'} as Record<string,string>)[tool]||tool;}
  useVersion(value:Version){this.enabled=value.definition.enabled;this.instructions=value.definition.instructions;this.tools=[...value.definition.tools];this.notice.set('Versão histórica carregada no formulário. Publique para criar uma nova versão.');}
  async save(){const current=this.selected();if(!current||this.busy())return;this.busy.set(true);this.error.set(null);try{await this.api.request('/assistants/admin/'+current.id,'PUT',{expected_revision:current.revision,enabled:this.enabled,instructions:this.instructions,tools:this.tools});this.notice.set('Nova versão publicada e registrada na auditoria.');await this.load();}catch(e){this.error.set(e);}finally{this.busy.set(false);}}
}
