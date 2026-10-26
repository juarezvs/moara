import { Component,Input } from '@angular/core';
import { ApiError } from './api';

@Component({selector:'moara-error',standalone:true,template:`@if(error){<div class="error-box" role="alert"><strong>{{text}}</strong>@if(requestId){<small>Solicitação {{requestId}}</small>}</div>}`})
export class ErrorBox {
  @Input()error:unknown;
  get text(){return this.error instanceof Error?this.error.message:'Confira os campos informados.';}
  get requestId(){return this.error instanceof ApiError?this.error.requestId:'';}
}
@Component({selector:'moara-loading',standalone:true,template:'<div class="loading" role="status"><span></span>Carregando…</div>'})
export class Loading {}
export function bytes(value:number|null|undefined){
  if(value==null||!Number.isFinite(value)||value<0)return 'Não disponível';
  if(value<1024)return value+' B';
  const unit=Math.min(4,Math.floor(Math.log(value)/Math.log(1024)));
  return (value/Math.pow(1024,unit)).toLocaleString('pt-BR',{maximumFractionDigits:1})+' '+['B','KiB','MiB','GiB','TiB'][unit];
}
