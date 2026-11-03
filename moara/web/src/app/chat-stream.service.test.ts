import {afterEach,describe,expect,it,vi} from 'vitest';
import {ChatStreamService} from './chat-stream.service';
const bytes=(s:string)=>new TextEncoder().encode(s);
const event=(content:string)=>'data: '+JSON.stringify({choices:[{delta:{content}}]})+'\n\n';
const options=(onText=vi.fn())=>({csrf:'synthetic',signal:new AbortController().signal,onText});
function transport(){
 let writer!:ReadableStreamDefaultController<Uint8Array>;
 const stream=new ReadableStream<Uint8Array>({start(c){writer=c;}});
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(stream,{headers:{'Content-Type':'text/event-stream'}})));
 return {push:(s:string)=>writer.enqueue(bytes(s)),close:()=>writer.close(),fail:()=>writer.error(new DOMException('Aborted','AbortError'))};
}
async function tick(){for(let i=0;i<10;i++)await Promise.resolve();}
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();});
describe('ChatStreamService',()=>{
 it('moves from thinking to streaming and completes without losing text',async()=>{
  const wire=transport();const service=new ChatStreamService();const opt=options();
  const run=service.run({},opt);expect(service.status()).toBe('thinking');
  wire.push(event('Olá'));await tick();expect(service.status()).toBe('streaming');expect(service.text()).toBe('Olá');
  wire.push(event(' Moara'));wire.push('data: [DONE]\n\n');await run;
  expect(service.status()).toBe('completed');expect(service.text()).toBe('Olá Moara');
  expect(opt.onText).toHaveBeenLastCalledWith('Olá Moara');
 });
 it('batches bursts rather than rerendering once per token',async()=>{
  vi.useFakeTimers();const wire=transport();const service=new ChatStreamService();const opt=options();
  const run=service.run({},opt);wire.push(event('a'));await tick();
  for(let i=0;i<100;i++)wire.push(event('b'));await tick();
  expect(opt.onText.mock.calls.length).toBeLessThan(5);
  wire.push('data: [DONE]\n\n');await run;
  expect(service.text()).toBe('a'+'b'.repeat(100));expect(vi.getTimerCount()).toBe(0);
 });
 it('preserves the partial answer and clears state on transport failure',async()=>{
  const wire=transport();const service=new ChatStreamService();const opt=options();
  const run=service.run({},opt);const failure=expect(run).rejects.toThrow();
  wire.push(event('Texto parcial'));await tick();wire.push(event(' preservado'));await tick();wire.fail();
  await failure;expect(service.text()).toBe('Texto parcial preservado');expect(service.status()).toBe('idle');
 });
 it('does not treat EOF without DONE as successful completion',async()=>{
  const wire=transport();const service=new ChatStreamService();const run=service.run({},options());
  const failure=expect(run).rejects.toThrow('confirmação');wire.push(event('Recebido'));wire.close();await failure;
  expect(service.text()).toBe('Recebido');expect(service.status()).toBe('idle');
 });
 it('forwards actual progress and rejects SSE errors',async()=>{
  const wire=transport();const service=new ChatStreamService();const onEvent=vi.fn();
  const run=service.run({},{...options(),onEvent});const failure=expect(run).rejects.toThrow();
  wire.push('data: {"moara_progress":{"stage":"checking","label":"Conferindo fontes"}}\n\n');await tick();
  expect(service.status()).toBe('thinking');expect(onEvent).toHaveBeenCalled();
  wire.push('data: {"error":{"status":503,"code":"inference_unavailable"}}\n\n');await failure;
  expect(service.status()).toBe('idle');
 });
 it('rejects overlapping requests and recovers for the next turn',async()=>{
  const wire=transport();const service=new ChatStreamService();const run=service.run({},options());
  await expect(service.run({},options())).rejects.toThrow('andamento');
  wire.push('data: [DONE]\n\n');await run;service.reset();expect(service.status()).toBe('idle');
 });
});
