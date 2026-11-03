import {Component,ChangeDetectionStrategy,input} from '@angular/core';
export interface UploadProgress {filename:string;loaded:number;total:number;percent:number;phase:'sending'|'confirming'|'stored'|'indexing'|'complete'|'error';index?:number;count?:number;}
export function uploadPercent(loaded:number,total:number){return total>0?Math.min(100,Math.max(0,Math.floor(loaded/total*100))):0;}
@Component({selector:'moara-upload-progress',standalone:true,changeDetection:ChangeDetectionStrategy.OnPush,template:`
 @if(state();as s){<section class="upload-progress" aria-label="Progresso do envio">
 <div><strong>{{s.filename}}</strong><span>{{s.percent}}%</span></div>
 <progress max="100" [value]="s.percent" [attr.aria-label]="'Upload de '+s.filename" [attr.aria-valuetext]="s.percent+'% enviado'"></progress>
 <p role="status">{{s.phase==='sending'?'Enviando arquivo…':s.phase==='confirming'?'Envio de 100% concluído. Confirmando armazenamento…':s.phase==='stored'?'Arquivo armazenado.':s.phase==='indexing'?'Upload concluído. Extraindo o texto e indexando o documento…':s.phase==='error'?'Não foi possível concluir. Confira a mensagem de erro.':'Documento pronto.'}}@if(s.count && s.count > 1){ <span>Arquivo {{s.index}} de {{s.count}}.</span>}</p>
 </section>}`,styles:[`:host{display:block;min-width:0}.upload-progress{padding:14px 18px;border:1px solid var(--border,#dce3e8);border-radius:10px;background:var(--panel,#fff);color:var(--text,#192f46);margin:12px 0}.upload-progress>div{display:flex;justify-content:space-between;gap:15px;font-size:13px}.upload-progress strong{overflow-wrap:anywhere;min-width:0}.upload-progress progress{display:block;width:100%;max-width:none;height:8px;margin:10px 0;accent-color:var(--primary,#315d75)}.upload-progress p{font-size:12px;color:var(--muted,#596b7c);margin:0;line-height:1.6}`]})
export class UploadProgressView {state=input<UploadProgress|null>(null);}
