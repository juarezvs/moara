"""Synthetic measurements through the actual Moara HTTP chat route."""
import sys,json,time,ssl,pathlib,importlib.util,urllib.request,concurrent.futures
ROOT=pathlib.Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py')
maintenance=importlib.util.module_from_spec(spec);spec.loader.exec_module(maintenance)
token=maintenance.admin_session()
mode=sys.argv[1]
base='https://localhost:8443/moara' if mode=='cpu' else 'http://127.0.0.1:18075'
tls=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/ai-root-ca.crt'))
out=ROOT/'docs/runtime'/('gpu-validation-'+mode+'.json')
samples=[]
def measure(profile,case,rep):
 context=' '.join(f'Item {i}: a equipe fictícia Alfa recebe pedidos, confere os documentos e responde em cinco dias úteis. O responsável fictício é Bruno Exemplo.' for i in range(1,26))
 prompt=('Resuma em três tópicos o fluxo de atendimento de uma equipe fictícia: receber pedido, conferir documentos, responder em cinco dias úteis. Não invente outras etapas.' if case=='short' else context+'\nCom base somente nesses itens, informe o prazo e o responsável e apresente um resumo em três tópicos.')
 if profile=='qwen25-coder-7b' and case=='short':prompt='Escreva uma função Python soma_pares(valores) que some apenas os números pares de uma lista. Inclua dois exemplos com resultados. Não use bibliotecas.'
 payload={'model':profile,'messages':[{'role':'user','content':prompt}],'stream':True,'max_tokens':128,'temperature':0,'seed':42,'stream_options':{'include_usage':True}}
 request=urllib.request.Request(base+'/api/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 start=time.monotonic();first=None;answer='';reasoning='';usage={};meta={};done=False;finish=None
 try:
  with urllib.request.urlopen(request,context=tls,timeout=360) as response:
   status=response.status
   for line in response:
    line=line.decode().strip()
    if not line.startswith('data:'):continue
    value=line[5:].strip()
    if value=='[DONE]':done=True;break
    value=json.loads(value)
    if 'moara' in value:meta.update(value['moara'])
    if value.get('usage'):usage=value['usage']
    for choice in value.get('choices',[]):
     delta=choice.get('delta',{});text=delta.get('content','') or ''
     if text and first is None:first=time.monotonic()-start
     answer+=text;reasoning+=delta.get('reasoning','') or ''
     if choice.get('finish_reason'):finish=choice['finish_reason']
  elapsed=time.monotonic()-start
  result={'mode':mode,'profile':profile,'case':case,'repetition':rep,'status':status,'ttft_seconds':first,'elapsed_seconds':elapsed,'usage':usage,'moara':meta,'stream_done':done,'finish_reason':finish,'answer':answer,'reasoning_chars':len(reasoning)}
  n=usage.get('completion_tokens')
  result['end_to_end_output_tokens_per_second']=n/elapsed if n else None
  result['approx_stream_tokens_per_second']=max(0,n-1)/(elapsed-first) if n and first is not None and elapsed>first else None
 except Exception as exc:
  result={'mode':mode,'profile':profile,'case':case,'repetition':rep,'error':type(exc).__name__,'elapsed_seconds':time.monotonic()-start}
  if hasattr(exc,'read'):result['detail']=exc.read().decode()[:500]
 print(json.dumps({k:v for k,v in result.items() if k not in ('answer','reasoning_chars')},ensure_ascii=False),flush=True)
 return result

if __name__=='__main__':
 for profile in ['fast','qwen25-coder-7b','gemma4-12b']:
  for case in ['short','long']:
   for rep in range(3):
    samples.append(measure(profile,case,rep))
    out.write_text(json.dumps({'synthetic_only':True,'mode':mode,'base':base,'max_output_tokens':128,'samples':samples},ensure_ascii=False,indent=2))
    if samples[-1].get('error'):break
 print('RESULT_FILE='+str(out),flush=True)
