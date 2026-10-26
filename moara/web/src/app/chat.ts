import { Component,inject,signal,OnDestroy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { Api,ApiError } from './api';
import { Auth } from './auth';
import { ErrorBox } from './ui';
import { SseDecoder } from './sse';
interface Profile {id:string;name:string;available:boolean;}
interface Message {role:'user'|'assistant';content:string;status?:'completed'|'interrupted';}
interface Chat {id:string;title:string;profile_id:string;updated_at:string;messages?:Message[];}
interface Routing {profile:string;model_name:string|null;reason:string;inference_used:boolean;identity_version:string;}
interface StreamChunk {error?:{message?:string};moara?:Routing;choices?:{delta?:{content?:string}}[];}
interface DataRun {id:string;status:string;error?:string;result?:{answer?:string;moara?:Routing;sources?:{name:string;objects:string[]}[];};}
@Component({standalone:true,imports:[FormsModule,DatePipe,ErrorBox],template:`
<div class="page-header"><div><span class="eyebrow">CONVERSAS / MOARA AI</span><h1>Como posso ajudar você hoje?</h1><p>Desenvolva, estude e crie com sua IA local.</p></div><button class="secondary" [disabled]="busy()" (click)="newChat()">＋ Novo chat</button></div>
<moara-error [error]="error()"/><div class="chat-workbench"><aside class="panel conversation-list"><h2>Conversas</h2><p class="muted small">As conversas anteriores continuam no <a href="/">chat institucional</a>.</p>@for(c of history();track c.id){<button class="history-item" [class.selected]="current()?.id===c.id" (click)="open(c)" [disabled]="busy()"><strong>{{c.title}}</strong><small>{{c.updated_at|date:'dd/MM HH:mm'}}</small></button>}@empty{<p class="muted">Suas novas conversas aparecerão aqui.</p>}</aside>
<section class="chat-panel panel"><div class="chat-options"><label>Perfil<select name="profile" [(ngModel)]="profile" [disabled]="busy()"><option value="auto">Seleção automática</option>@for(p of profiles();track p.id){<option [value]="p.id" [disabled]="!p.available">{{p.name}}{{p.available?'':' · indisponível'}}</option>}</select></label>@if(routing()){<span class="small muted" role="status">{{routing()!.inference_used?routing()!.model_name:'Identidade institucional'}} · {{routing()!.identity_version}}@if(routing()!.reason.includes('fallback')){ ? Perfil alternativo compat?vel utilizado}</span>}</div>
<div class="messages" aria-live="polite" aria-relevant="additions">@for(m of messages();track $index){<article class="message" [class.user-message]="m.role==='user'"><strong>{{m.role==='user'?'Você':'Moara'}}</strong><div class="markdown" [innerHTML]="render(m.content)"></div>@if(m.status==='interrupted'){<small class="badge warning">Resposta interrompida</small>}</article>}@empty{<div class="chat-welcome"><img src="brand/mark.svg" alt=""><h2>Moara</h2><p>Sua IA local, segura e privada.</p><div class="prompt-grid"><button (click)="draft='Quem é você?'">Conheça a Moara ↗</button><button (click)="draft='Explique como escrever testes de software.'">Desenvolva com testes ↗</button><button (click)="draft='Explique o que é uma API.'">Aprenda algo novo ↗</button></div></div>}</div>
@if(busy()){<div class="stream-status" role="status"><span class="spinner"></span> {{received()?'Recebendo resposta…':'Aguardando o modelo…'}} <button class="secondary" (click)="stop()">Interromper</button></div>}
<form class="chat-composer" (ngSubmit)="send()"><label class="sr-only" for="chat-draft">Sua mensagem</label><textarea id="chat-draft" name="draft" [(ngModel)]="draft" placeholder="Digite sua mensagem aqui…" rows="3" maxlength="12000" [disabled]="busy()" required></textarea>@if(auth.can('data.query')){<label class="check-label query-mode"><input type="checkbox" name="dataMode" [(ngModel)]="dataMode" [disabled]="busy()||!planners().length">Consultar fontes autorizadas <span class="badge">Somente leitura</span></label>}<div class="composer-actions"><span class="muted small">Revise informações importantes antes de utilizá-las.</span><button class="primary" [disabled]="busy()||!draft.trim()||profiles().length===0">Enviar ↑</button></div></form>
@if(messages().length&&!busy()){<div class="conversation-actions"><button class="text-button" (click)="regenerate()">Gerar novamente</button><button class="text-button" (click)="exportChat()">Exportar conversa</button><button class="text-button danger" (click)="deletePending.set(true)">Excluir conversa</button></div>}
</section></div>
@if(deletePending()){<section class="confirm-inline panel" role="alertdialog" aria-labelledby="delete-chat-title"><h2 id="delete-chat-title">Excluir esta conversa?</h2><p>A exclusão afeta somente esta conversa da nova plataforma.</p><button class="secondary" (click)="deletePending.set(false)">Cancelar</button><button class="primary" (click)="remove()">Confirmar exclusão</button></section>}
`})
export class ChatPage implements OnDestroy {
  auth=inject(Auth);dataMode=false;planners=signal<string[]>([]);dataRunId:string|null=null;
  api=inject(Api);profiles=signal<Profile[]>([]);history=signal<Chat[]>([]);current=signal<Chat|null>(null);messages=signal<Message[]>([]);error=signal<unknown>(null);busy=signal(false);received=signal(false);routing=signal<Routing|null>(null);deletePending=signal(false);profile='auto';draft='';controller:AbortController|null=null;
  constructor(){void this.load();}
  async load(){try{const [p,h]=await Promise.all([this.api.request<Profile[]>('/models/profiles'),this.api.request<Chat[]>('/chats')]);this.profiles.set(p);this.history.set(h);if(this.auth.can('data.query')){try{const planners=await this.api.request<{id:string;reliable_tools:boolean}[]>('/connectors/models');this.planners.set(planners.filter(m=>m.reliable_tools).map(m=>m.id));}catch{this.planners.set([]);}}}catch(e){this.error.set(e);}}
  render(content:string){return DOMPurify.sanitize(marked.parse(content,{async:false}) as string,{FORBID_TAGS:['form','input','button','iframe','object','style'],FORBID_ATTR:['style']});}
  newChat(){if(this.busy())return;this.current.set(null);this.messages.set([]);this.routing.set(null);this.error.set(null);this.deletePending.set(false);}
  async open(c:Chat){if(this.busy())return;try{const result=await this.api.request<Chat>('/chats/'+c.id);this.current.set(result);this.messages.set(result.messages||[]);this.profile=result.profile_id;this.routing.set(null);}catch(e){this.error.set(e);}}
  async persist(){const c=this.current();if(!c)return;const result=await this.api.request<{updated_at:string}>('/chats/'+c.id,'PUT',{title:this.messages().find(m=>m.role==='user')?.content.slice(0,80)||'Novo chat',profile_id:this.profile,expected_updated_at:c.updated_at,messages:this.messages()});this.current.set({...c,updated_at:result.updated_at});await this.load();}
  async send(regenerate=false){
    if(this.busy()||(!regenerate&&!this.draft.trim()))return;this.busy.set(true);this.received.set(false);this.error.set(null);this.controller=new AbortController();
    if(!regenerate){this.messages.update(m=>[...m,{role:'user',content:this.draft.trim()}]);this.draft='';}
    const input=this.messages().map(({role,content})=>({role,content}));let answer='';let completed=false;
    const timeout=setTimeout(()=>this.controller?.abort('timeout'),1200000);
    try{
      if(!this.current())this.current.set(await this.api.request<Chat>('/chats','POST',{title:input[0]?.content.slice(0,80)||'Novo chat'}));
      await this.persist();
      if(this.dataMode){await this.dataAnswer(input.at(-1)?.content||'');completed=true;return;}
      const response=await fetch('/moara/api/v1/chat/stream',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Moara-CSRF':this.api.csrf()},body:JSON.stringify({model:this.profile,messages:input,stream:true}),signal:this.controller.signal});
      if(!response.ok){const result=await response.json().catch(()=>({}));throw new ApiError(response.status,typeof result.detail==='string'?result.detail:'internal_error',response.headers.get('X-Request-ID')||'');}
      if(!response.body)throw new Error('O servidor não abriu o fluxo de resposta.');
      this.messages.update(m=>[...m,{role:'assistant',content:''}]);const reader=response.body.getReader();const decoder=new SseDecoder<StreamChunk>();
      while(true){const next=await reader.read();if(next.done)break;
        for(const chunk of decoder.feed(next.value)){if(chunk==='[DONE]'){completed=true;continue;}if(chunk.error)throw new Error(chunk.error.message||'Resposta interrompida.');if(chunk.moara)this.routing.set(chunk.moara);for(const choice of chunk.choices||[]){if(choice.delta?.content){answer+=choice.delta.content;this.received.set(true);this.messages.update(m=>[...m.slice(0,-1),{role:'assistant',content:answer}]);}}}
      }
      if(!completed)throw new Error('A resposta terminou antes da confirmação do servidor. Você pode gerar novamente.');
    }catch(e){if(this.controller?.signal.aborted)this.error.set(new Error(this.controller.signal.reason==='timeout'?'O tempo de geração foi excedido.':'Geração interrompida. O texto recebido foi preservado.'));else this.error.set(e);}
    finally{clearTimeout(timeout);this.controller=null;this.messages.update(m=>m.filter(v=>v.content.length>0).map((v,i,all)=>!completed&&i===all.length-1&&v.role==='assistant'?{...v,status:'interrupted' as const}:v));try{await this.persist();}catch(e){this.error.set(e);}this.busy.set(false);}
  }
  async regenerate(){if(this.busy())return;this.messages.update(m=>m[m.length-1]?.role==='assistant'?m.slice(0,-1):m);if(this.messages().at(-1)?.role==='user')await this.send(true);}
  async dataAnswer(question:string){
    const planner=this.profile==='auto'?(this.planners().includes('coding')?'coding':this.planners()[0]):this.profile;
    if(!planner||!this.planners().includes(planner))throw new Error('Selecione um perfil com ferramentas de consulta validadas ou use a seleção automática.');
    const queued=await this.api.request<DataRun>('/connectors/ask','POST',{question,model:planner});this.dataRunId=queued.id;
    try{while(true){if(this.controller?.signal.aborted)throw new DOMException('Cancelled','AbortError');const run=await this.api.request<DataRun>('/connectors/runs/'+queued.id);
      if(run.status==='completed'){const answer=run.result?.answer;if(!answer)throw new Error('A consulta terminou sem resposta textual.');let text=answer;const sources=run.result?.sources||[];if(sources.length)text+='\n\n**Fontes consultadas:** '+sources.map(s=>s.name.replace(/[\[\]<>]/g,'')+' ('+s.objects.join(', ')+')').join('; ')+'.';this.messages.update(m=>[...m,{role:'assistant',content:text}]);if(run.result?.moara)this.routing.set(run.result.moara);this.received.set(true);return;}
      if(['failed','cancelled'].includes(run.status))throw new Error(run.error||'A consulta não foi concluída.');await new Promise(resolve=>setTimeout(resolve,1500));}
    }finally{if(this.controller?.signal.aborted)await this.api.request('/connectors/runs/'+queued.id+'/cancel','POST');this.dataRunId=null;}
  }
  stop(){this.controller?.abort();if(this.dataRunId)void this.api.request('/connectors/runs/'+this.dataRunId+'/cancel','POST').catch(()=>{});}
  ngOnDestroy(){this.stop();}
  async remove(){const c=this.current();if(!c)return;try{await this.api.request('/chats/'+c.id,'DELETE');this.newChat();await this.load();}catch(e){this.error.set(e);}}
  exportChat(){const blob=new Blob([this.messages().map(m=>'## '+(m.role==='user'?'Você':'Moara')+'\n\n'+m.content).join('\n\n')],{type:'text/markdown;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='moara-conversa.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
}
