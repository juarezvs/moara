import { Component,inject,signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router,RouterLink } from '@angular/router';
import { Auth } from './auth';
import { ErrorBox } from './ui';

@Component({standalone:true,imports:[FormsModule,RouterLink,ErrorBox],template:`
<main class="login-scene"><section class="login-intro"><div class="large-brand"><img src="brand/mark.svg" alt=""><h1>Moara <small>AI</small></h1></div><p class="intro-tagline">Sua IA local, segura e privada</p><p class="intro-promise">Inteligência artificial ao seu lado,<br>com total privacidade. Seus dados. No seu ambiente.</p><div class="values"><div><span>◇</span><strong>100% Local</strong><small>Seus dados ficam<br>com você</small></div><div><span>▣</span><strong>Privacidade</strong><small>Informação protegida<br>no seu ambiente</small></div><div><span>ϟ</span><strong>Alta performance</strong><small>Inteligência a serviço<br>das pessoas</small></div></div></section>
<section class="login-card glass"><div class="brand"><img src="brand/mark.svg" alt=""><strong>Moara <small>AI</small></strong></div><h2>Faça login no Moara AI</h2><p>Acesso à sua IA local, segura e privada.</p>
<form (ngSubmit)="submit()"><label>E-mail<input name="email" type="email" [(ngModel)]="email" autocomplete="username" placeholder="Digite seu e-mail" required maxlength="200"></label><label>Senha<div class="password-field"><input name="password" [type]="visible()?'text':'password'" [(ngModel)]="password" autocomplete="current-password" placeholder="Digite sua senha" required maxlength="256"><button type="button" (click)="visible.set(!visible())" [attr.aria-label]="visible()?'Ocultar senha':'Mostrar senha'">{{visible()?'◉':'◎'}}</button></div></label>@if(auth.notice()){<p role="status">{{auth.notice()}}</p>}<moara-error [error]="error()"/><button class="primary" [disabled]="busy()">{{busy()?'Entrando…':'Entrar'}}<span>→</span></button></form>
<a class="institutional-login" href="/">Usar o chat institucional →</a><div class="secure-badge">▣ IA Local <span>·</span> Ambiente Seguro</div><a class="about-link" routerLink="/sobre">Sobre a Moara</a></section></main>`})
export class Login {
  auth=inject(Auth);router=inject(Router);email='';password='';visible=signal(false);busy=signal(false);error=signal<unknown>(null);
  async submit(){if(this.busy())return;this.busy.set(true);this.error.set(null);try{await this.auth.login(this.email.trim(),this.password);this.password='';await this.router.navigateByUrl('/');}catch(e){this.error.set(e);}finally{this.busy.set(false);}}
}
