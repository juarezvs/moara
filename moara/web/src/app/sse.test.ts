import { describe,it,expect } from 'vitest';
import { SseDecoder } from './sse';
const encode=(value:string)=>new TextEncoder().encode(value);
describe('real chat SSE transport',()=>{
  it('preserves UTF-8 when every byte arrives separately',()=>{
    const decoder=new SseDecoder<{text:string}>();const result:unknown[]=[];
    for(const byte of encode('data: {"text":"Você é Moara"}\n\ndata: [DONE]\n\n'))result.push(...decoder.feed(new Uint8Array([byte])));
    expect(result).toEqual([{text:'Você é Moara'},'[DONE]']);
  });
  it('handles CRLF, heartbeats and multiple events in one read',()=>{
    const decoder=new SseDecoder<{ok:boolean}>();
    expect(decoder.feed(encode(': keepalive\r\n\r\ndata: {"ok":true}\r\n\r\ndata: [DONE]\r\n\r\n'))).toEqual([{ok:true},'[DONE]']);
  });
  it('never treats a partial event as a completed answer',()=>{
    const decoder=new SseDecoder<{ok:boolean}>();
    expect(decoder.feed(encode('data: {"ok":'))).toEqual([]);
    expect(decoder.feed(encode('true}\n\n'))).toEqual([{ok:true}]);
  });
  it('rejects malformed or unbounded events without exposing raw content',()=>{
    expect(()=>new SseDecoder().feed(encode('data: private-invalid-value\n\n'))).toThrow('evento de resposta inválido');
    expect(()=>new SseDecoder().feed(encode('data: '+ 'x'.repeat(262145)))).toThrow('limite permitido');
  });
});
