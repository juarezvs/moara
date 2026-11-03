import {Component,inject,signal,output} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {DatePipe} from '@angular/common';
import {Api} from './api';
import {ErrorBox} from './ui';
interface Thesis {theme:number;bank:'com'|'sem';thesis_text:string;leading_case:string|null;displayed_event_date:string;source:string;andamento_url:string|null;acordao_search_url:string|null;}
interface Catalogue {available:boolean;items:Thesis[];total:number;page:number;limit:number;version?:string;collected_at?:string;counts?:{com:number;sem:number};notice:string;}
@Component({selector:'moara-stf-theses',standalone:true,imports:[FormsModule,DatePipe,ErrorBox],template:`
 <div class="stf-heading"><div><h2>Acervo de teses do STF</h2><p>Teses divulgadas com e sem repercussão geral.</p></div><button type="button" class="secondary" [disabled]="downloading()" (click)="download()">{{downloading()?'Preparando arquivo...':'Baixar acervo e fontes'}}</button></div>
 @if(result();as r){
  <p class="stf-notice">{{r.notice}}</p>
  @if(r.available){<div class="stf-summary"><span><strong>{{r.counts?.com}}</strong> com repercussão geral</span><span><strong>{{r.counts?.sem}}</strong> sem repercussão geral</span><span>Coleta: {{r.collected_at|date:'dd/MM/yyyy HH:mm'}}</span></div>}
 }
 <form class="stf-search" (ngSubmit)="load(1)"><label>Buscar por palavras ou número do tema<input name="query" [(ngModel)]="query" maxlength="160" placeholder="Ex.: ICMS PIS COFINS ou 69"></label><label>Banco<select aria-label="Banco" name="bank" [(ngModel)]="bank" (ngModelChange)="load(1)"><option value="all">Todos</option><option value="com">Com repercussão geral</option><option value="sem">Sem repercussão geral</option></select></label><button class="primary" [disabled]="busy()">Pesquisar teses</button></form>
 <moara-error [error]="error()"/>
 <p role="status" aria-live="polite">{{busy()?'Consultando o acervo…':result()?.available?(result()!.total+' registro(s) encontrado(s).'):'Acervo ainda não disponível.'}}</p>
 @if(result();as r){
  <div class="stf-results">@for(item of r.items;track $index){<article class="stf-card"><div class="stf-card-title"><h3>Tema {{item.theme}}</h3><span [class.no-rg]="item.bank==='sem'" class="stf-badge">{{item.bank==='com'?'Com repercussão geral':'Sem repercussão geral'}}</span></div><small>{{item.leading_case||'Processo não informado no catálogo'}} · Data do andamento no catálogo: {{item.displayed_event_date||'não informada'}}</small><p class="stf-thesis">{{item.thesis_text}}</p><div class="stf-actions"><a [href]="item.source" target="_blank" rel="noopener noreferrer">Fonte oficial do tema ↗</a>@if(item.andamento_url){<a [href]="item.andamento_url" target="_blank" rel="noopener noreferrer">Andamentos ↗</a>}@if(item.acordao_search_url){<a [href]="item.acordao_search_url" target="_blank" rel="noopener noreferrer">Pesquisar acórdão ↗</a>}<button type="button" class="secondary" (click)="selected.emit(item.theme)">Preparar conferência no chat</button></div></article>}@empty{@if(!busy()){<p>Nenhuma tese encontrada com esses filtros. Temas sem tese divulgada podem não constar deste acervo.</p>}}</div>
  @if(r.available){<nav class="stf-pages" aria-label="Páginas do acervo"><button class="secondary" [disabled]="busy()||r.page<=1" (click)="load(r.page-1)">Anterior</button><span>Página {{r.page}} · {{r.total}} registro(s)</span><button class="secondary" [disabled]="busy()||r.page*r.limit>=r.total" (click)="load(r.page+1)">Próxima</button></nav>}
 }
 `,styleUrl:'./stf-theses.css'})
export class STFTheses {
 api=inject(Api);result=signal<Catalogue|null>(null);busy=signal(false);error=signal<unknown>(null);selected=output<number>();downloading=signal(false);query='';bank='all';
 constructor(){void this.load(1);}
 async download(){if(this.downloading())return;this.downloading.set(true);this.error.set(null);try{const value=await this.api.request<unknown>('/legal/stf-theses/export');const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json;charset=utf-8'}));const anchor=document.createElement('a');anchor.href=url;anchor.download='moara-stf-teses.json';anchor.click();setTimeout(()=>URL.revokeObjectURL(url),10000);}catch(error){this.error.set(error);}finally{this.downloading.set(false);}}
 async load(page:number){if(this.busy())return;this.busy.set(true);this.error.set(null);try{const q=this.query.trim();const params=new URLSearchParams({bank:this.bank,page:String(page),limit:'20',...(/^\d{1,5}$/.test(q)?{theme:q}:{query:q})});const value=await this.api.request<Catalogue>('/legal/stf-theses?'+params);this.result.set(value);}catch(error){this.error.set(error);}finally{this.busy.set(false);}}
}
