/** Incremental UTF-8/SSE decoding shared by the real chat and transport tests. */
export class SseDecoder<T> {
  private decoder=new TextDecoder();
  private pending='';
  feed(bytes:Uint8Array):(T|'[DONE]')[]{
    this.pending=(this.pending+this.decoder.decode(bytes,{stream:true})).replace(/\r\n/g,'\n');
    if(this.pending.length>262144)throw new Error('O servidor enviou um evento maior que o limite permitido.');
    const events:(T|'[DONE]')[]=[];let position:number;
    while((position=this.pending.indexOf('\n\n'))>=0){
      const block=this.pending.slice(0,position);this.pending=this.pending.slice(position+2);
      const data=block.split('\n').filter(line=>line.startsWith('data:')).map(line=>line.slice(5).trimStart()).join('\n').trim();
      if(!data)continue;
      if(data==='[DONE]'){events.push('[DONE]');continue;}
      try{const value=JSON.parse(data);if(!value||typeof value!=='object'||Array.isArray(value))throw new Error();events.push(value as T);}
      catch{throw new Error('O servidor enviou um evento de resposta inválido.');}
    }
    return events;
  }
}
