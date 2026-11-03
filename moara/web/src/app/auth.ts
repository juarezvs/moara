import { Injectable,inject,signal } from '@angular/core';
import { CanActivateFn,Router } from '@angular/router';
import { Api,ApiError } from './api';

export interface User {id:string;subject:string;name:string;email:string|null;roles:string[];permissions:string[];auth_source:string;csrf_token:string|null;password_change_required:boolean;preferences:{theme:'light'|'dark';welcome_seen:boolean};}
export interface LoginResult {authenticated?:boolean;csrf_token?:string;mfa_required?:boolean;next_step?:'enroll'|'verify'|'recover';challenge_token?:string;expires_in?:number;recovery_codes?:string[];}
@Injectable({providedIn:'root'})
export class Auth {
  private api=inject(Api);user=signal<User|null>(null);theme=signal<'light'|'dark'>('light');notice=signal<string|null>(null);
  async initialize(){
    try{await this.refresh();}
    catch(error){
      if(!(error instanceof ApiError)||error.status!==401)return;
      let token='';try{token=localStorage.getItem('token')||'';}catch{}
      if(token&&token.length<4096){
        try{
          const response=await fetch('/moara/api/v1/auth/session',{method:'POST',credentials:'same-origin',headers:{Authorization:'Bearer '+token},signal:AbortSignal.timeout(15000)});
          if(response.ok)await this.refresh();
        }catch{}
      }
    }
    if(!this.user())this.applyTheme('light');
  }
  async refresh(){const user=await this.api.request<User>('/auth/me');this.user.set(user);this.api.csrf.set(user.csrf_token||'');this.applyTheme(user.preferences?.theme==='dark'?'dark':'light');return user;}
  async login(email:string,password:string){
    const result=await this.api.request<LoginResult>('/auth/login','POST',{email,password});
    if(result.authenticated)await this.acceptSession(result);return result;
  }
  async acceptSession(result:LoginResult){this.api.csrf.set(result.csrf_token||'');await this.refresh();}
  async logout(){const result=await this.api.request<{legacy_logout_confirmed:boolean}>('/auth/logout','POST');try{localStorage.removeItem('token');}catch{}this.user.set(null);this.api.csrf.set('');if(!result.legacy_logout_confirmed)this.notice.set('A sessão Moara foi encerrada. Não foi possível confirmar o encerramento da sessão do chat institucional; feche as abas do chat.');}
  can(permission:string){return !!this.user()?.permissions.some(p=>p==='*'||p===permission);}
  applyTheme(value:'light'|'dark'){this.theme.set(value);document.documentElement.dataset['theme']=value;}
  async toggleTheme(){const value=this.theme()==='light'?'dark':'light';try{await this.api.request('/auth/preferences','PUT',{theme:value});this.applyTheme(value);}catch{this.notice.set('Não foi possível salvar sua preferência de tema. Tente novamente.');}}
}
export const signedIn:CanActivateFn=(_route,state)=>{const auth=inject(Auth),router=inject(Router);return !auth.user()?router.createUrlTree(['/login'],{queryParams:{returnTo:state.url}}):auth.user()!.password_change_required&&state.url!=='/senha'?router.createUrlTree(['/senha']):true;};
export const allowed=(permission:string):CanActivateFn=>()=>{const auth=inject(Auth),router=inject(Router);return auth.can(permission)?true:router.createUrlTree(['/chat']);};
