import {Injectable,signal} from '@angular/core';
import {ApiError} from './api';
import {SseDecoder} from './sse';

export type ChatStreamStatus='idle'|'thinking'|'streaming'|'completed';
export interface ChatStreamEvent {
  error?:{message?:string;status?:number;code?:string};
  moara_progress?:{stage:string;label:string};
  moara?:unknown;
  choices?:{delta?:{content?:string}}[];
}
export interface StreamOptions {
  csrf:string;
  signal:AbortSignal;
  onText:(text:string)=>void;
  onEvent?:(event:ChatStreamEvent)=>void;
}

/** Transport and response state only; persistence and scrolling belong to the UI. */
@Injectable()
export class ChatStreamService {
  private state=signal<ChatStreamStatus>('idle');
  private response=signal('');
  readonly status=this.state.asReadonly();
  readonly text=this.response.asReadonly();
  private running=false;
  begin(){this.response.set('');this.state.set('thinking');}
  finish(completed:boolean){this.state.set(completed?'completed':'idle');}
  reset(){if(!this.running){this.response.set('');this.state.set('idle');}}

  async run(payload:Record<string,unknown>,options:StreamOptions):Promise<void> {
    if(this.running)throw new Error('Já existe uma resposta em andamento.');
    this.running=true;this.begin();
    let reader:ReadableStreamDefaultReader<Uint8Array>|undefined;
    let frame:ReturnType<typeof setTimeout>|undefined;
    let pending='';let answer='';let completed=false;
    const flush=()=>{
      if(frame!==undefined){clearTimeout(frame);frame=undefined;}
      if(!pending)return;
      answer+=pending;pending='';
      this.response.set(answer);options.onText(answer);
    };
    try {
      const response=await fetch('/moara/api/v1/chat/stream',{
        method:'POST',credentials:'same-origin',
        headers:{'Content-Type':'application/json','Accept':'text/event-stream','X-Moara-CSRF':options.csrf},
        body:JSON.stringify({...payload,stream:true}),signal:options.signal
      });
      if(!response.ok){
        const value=await response.json().catch(()=>({}));
        throw new ApiError(response.status,typeof value.detail==='string'?value.detail:'internal_error',response.headers.get('X-Request-ID')||'');
      }
      if(!response.body)throw new Error('O servidor não abriu o fluxo de resposta.');
      reader=response.body.getReader();
      const decoder=new SseDecoder<ChatStreamEvent>();
      while(!completed){
        const next=await reader.read();
        if(next.done)break;
        for(const event of decoder.feed(next.value)){
          if(event==='[DONE]'){completed=true;break;}
          if(event.error){
            if(event.error.status)throw new ApiError(event.error.status,event.error.code||'internal_error','');
            throw new Error(event.error.message||'Resposta interrompida.');
          }
          options.onEvent?.(event);
          for(const choice of event.choices||[]){
            const delta=choice.delta?.content;
            if(!delta)continue;
            pending+=delta;
            if(this.state()==='thinking'){this.state.set('streaming');flush();}
            else if(frame===undefined)frame=setTimeout(flush,32);
          }
        }
      }
      if(!completed)throw new Error('A resposta terminou antes da confirmação do servidor. Você pode gerar novamente.');
    } finally {
      // Persist every received character, including the last buffered fragment on cancel.
      flush();this.finish(completed);this.running=false;
      if(reader){try{await reader.cancel();}catch{}reader.releaseLock();}
    }
  }
}
