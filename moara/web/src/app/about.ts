import { Component,inject,signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from './api';
import { ErrorBox,Loading } from './ui';
export interface IdentityDocument {
  version:string;institutional_id:string;name:string;product:string;institution:string;purpose:string;presentation:string;
  origin:string;origin_status:string;origin_reference:string|null;principles:string[];limits:string[];declaration:string;signature:string;
  developer:string|null;institutional_approver:string|null;sha256:string;publication:{id:string;published_at:string;status:string;approval_source:string};
  faq?:{id:string;questions:string[];answer:string;dynamic:string}[];
}
@Component({standalone:true,imports:[RouterLink,ErrorBox,Loading],template:`
<div class="about-scene"><header class="about-nav"><a routerLink="/" class="brand"><img src="brand/mark.svg" alt=""><strong>Moara <small>AI</small></strong></a><div><a href="/">Abrir chat</a><a routerLink="/">Plataforma →</a></div></header><main class="about-content">
@if(error()){<moara-error [error]="error()"/>}@else if(!identity()){<moara-loading/>}@else{<section class="about-hero"><span class="eyebrow">JUSTIÇA FEDERAL DO AMAZONAS</span><img src="brand/mark.svg" alt="Logo Moara AI"><h1>Desenvolver.<br>Integrar. <em>Proteger.</em></h1><p>{{identity()!.presentation}}</p><div class="about-badges"><span>Inteligência local</span><span>Privacidade</span><span>Supervisão humana</span></div></section>
<section class="about-grid"><article class="panel"><div class="eyebrow">PROPÓSITO</div><h2>Tecnologia a serviço das pessoas.</h2><p>{{identity()!.purpose}}</p></article><article class="panel"><div class="eyebrow">NOSSAS RAÍZES</div><h2>Um nome com propósito.</h2><p>{{identity()!.origin}}</p></article></section>
<section class="about-section"><div class="eyebrow">PRINCÍPIOS INEGOCIÁVEIS</div><h2>O que orienta cada resposta.</h2><div class="principle-grid">@for(principle of identity()!.principles;track $index){<article class="panel"><span class="number">0{{$index+1}}</span><h3>{{principle}}</h3></article>}</div></section>
<section class="panel about-limits"><div><div class="eyebrow">RESPONSABILIDADE E TRANSPARÊNCIA</div><h2>Apoio técnico.<br>Responsabilidade humana.</h2></div><ul>@for(limit of identity()!.limits;track $index){<li>{{limit}}</li>}</ul></section>
<section class="declaration"><span>◇</span><blockquote>{{identity()!.declaration}}</blockquote><p>{{identity()!.signature}}</p></section>
<section class="panel governance"><h2>Governança institucional</h2><dl><div><dt>Versão do manifesto</dt><dd>{{identity()!.version}}</dd></div><div><dt>Identificador</dt><dd>{{identity()!.institutional_id}}</dd></div><div><dt>Responsável pelo desenvolvimento</dt><dd>{{identity()!.developer||'Não cadastrado'}}</dd></div><div><dt>Aprovador institucional</dt><dd>{{identity()!.institutional_approver||'Não cadastrado'}}</dd></div><div><dt>Integridade verificável</dt><dd class="hash">SHA-256 {{identity()!.sha256}}</dd></div></dl><p class="muted small">A publicação técnica inicial registra o manifesto fornecido para a implantação. A autoria, a aprovação formal e a etimologia não são presumidas.</p></section>}
</main><footer class="about-footer">Moara AI · Inteligência local, segura e privada.</footer></div>`})
export class About {
  private api=inject(Api);identity=signal<IdentityDocument|null>(null);error=signal<unknown>(null);
  constructor(){this.api.request<IdentityDocument>('/identity/public').then(v=>this.identity.set(v)).catch(e=>this.error.set(e));}
}
