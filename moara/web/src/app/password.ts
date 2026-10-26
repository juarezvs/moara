import { Component,inject,signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Api } from './api';
import { Auth } from './auth';
import { ErrorBox } from './ui';

@Component({standalone:true,imports:[FormsModule,ErrorBox],template:`<main class="password-page"><a href="/moara/" class="brand"><img src="brand/mark.svg" alt=""><strong>Moara AI</strong></a><section class="panel"><span class="eyebrow">SEGURANÇA DA SUA CONTA</span><h1>Defina sua senha</h1><p class="muted">Use pelo menos 16 caracteres. Escolha uma senha que você não utiliza em outros serviços.</p><form (ngSubmit)="submit()">@if(!auth.user()?.password_change_required){<label>Senha atual<input name="current" type="password" [(ngModel)]="current" autocomplete="current-password" required maxlength="256"></label>}<label>Nova senha<input name="password" type="password" [(ngModel)]="password" autocomplete="new-password" required minlength="16" maxlength="256"></label><label>Confirme a nova senha<input name="confirm" type="password" [(ngModel)]="confirm" autocomplete="new-password" required minlength="16" maxlength="256"></label><moara-error [error]="error()"/><button class="primary" [disabled]="busy()">{{busy()?'Salvando…':'Salvar senha'}}</button></form></section></main>`})
export class PasswordPage {
  api=inject(Api);auth=inject(Auth);router=inject(Router);current='';password='';confirm='';busy=signal(false);error=signal<unknown>(null);
  async submit(){if(this.password!==this.confirm){this.error.set(new Error('As senhas informadas não coincidem.'));return;}this.busy.set(true);this.error.set(null);try{await this.api.request('/auth/password','PUT',{password:this.password,current_password:this.current||null});this.current='';this.password='';this.confirm='';await this.auth.refresh();await this.router.navigateByUrl('/');}catch(e){this.error.set(e);}finally{this.busy.set(false);}}
}
