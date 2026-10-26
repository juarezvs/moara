import { Component,inject,signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from './api';
import { Auth } from './auth';
import { IdentityDocument } from './about';
import { Loading,ErrorBox } from './ui';
import { Operations } from './operations';

@Component({standalone:true,imports:[RouterLink,Loading,ErrorBox,Operations],template:`
<div class="page-header"><div><span class="eyebrow">MOARA AI · AMBIENTE INSTITUCIONAL</span><h1>Olá, {{auth.user()?.name?.split(' ')?.[0]}}.</h1><p>Desenvolva soluções, conecte informações e trabalhe com segurança.</p></div><a class="primary button-link" href="/">Abrir chat <span>→</span></a></div>
@if(error()){<moara-error [error]="error()"/>}@else if(!identity()){<moara-loading/>}@else{
@if(!auth.user()?.preferences?.welcome_seen){<div class="welcome-panel panel"><img src="brand/mark.svg" alt=""><div><div class="eyebrow">SUA ASSISTENTE INSTITUCIONAL</div><h2>Desenvolver, integrar e proteger.</h2><p>{{identity()!.purpose}}</p></div><a routerLink="/sobre" class="text-link">Conheça a Moara →</a><button class="icon-button" (click)="dismissWelcome()" aria-label="Ocultar boas-vindas">×</button></div>}
<div class="dashboard-cards"><a href="/" class="panel feature-card"><span class="feature-icon">‹/›</span><h2>Chat e desenvolvimento</h2><p>Converse com roteamento automático, anexos, ferramentas e seu histórico no chat Moara.</p><span class="text-link">Abrir chat →</span></a><a routerLink="/sobre" class="panel feature-card"><span class="feature-icon violet">◇</span><h2>Identidade e propósito</h2><p>Conheça o manifesto, os princípios e os limites da Moara.</p><span class="text-link">Sobre a Moara →</span></a>@if(auth.can('identity.draft')){<a routerLink="/identidade" class="panel feature-card"><span class="feature-icon cyan">◈</span><h2>Governança da identidade</h2><p>Consulte versões, prepare rascunhos e teste as respostas institucionais.</p><span class="text-link">Administrar identidade →</span></a>}</div>
<div class="notice"><span>▣</span><p>As respostas são apoio ao trabalho humano. O uso de dados e ferramentas respeita as permissões efetivamente autorizadas.</p></div>}
@if(auth.can('status.read')){<moara-operations/>}
`})
export class Dashboard {
  auth=inject(Auth);api=inject(Api);identity=signal<IdentityDocument|null>(null);error=signal<unknown>(null);
  async dismissWelcome(){try{await this.api.request('/auth/preferences','PUT',{welcome_seen:true});await this.auth.refresh();}catch(e){this.error.set(e);}}
  constructor(){this.api.request<IdentityDocument>('/identity').then(v=>this.identity.set(v)).catch(e=>this.error.set(e));}
}
