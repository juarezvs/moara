import json,time,pathlib,concurrent.futures,urllib.request,urllib.error
import measure_moara_gpu as bench
report={'synthetic_only':True,'checks':{},'samples':[]}
def call(body,authorized=True):
 headers={'Content-Type':'application/json'}
 if authorized:headers['Authorization']='Bearer '+bench.token
 req=urllib.request.Request(bench.base+'/api/v1/chat/completions',data=json.dumps(body).encode(),headers=headers)
 start=time.monotonic()
 try:
  with urllib.request.urlopen(req,timeout=300) as r:return r.status,json.load(r),time.monotonic()-start
 except urllib.error.HTTPError as e:return e.code,json.load(e),time.monotonic()-start
body={'model':'fast','messages':[{'role':'user','content':'Responda apenas teste.'}],'max_tokens':64}
status,_,_=call(body,False);report['checks']['unauthenticated_rejected']=status in (401,403)
status,_,_=call(dict(body,model='gpu-arbitrary-unapproved'));report['checks']['unapproved_model_rejected']=status==403
status,_,_=call(dict(body,messages=[{'role':'invalid','content':'teste'}]));report['checks']['invalid_message_rejected']=status==422
status,value,_=call(dict(body,messages=[{'role':'user','content':'Quem é você?'}]));report['checks']['institutional_identity_preserved']=status==200 and value.get('moara',{}).get('inference_used') is False and 'moara' in value['choices'][0]['message']['content'].lower()
report['residency_gemma']=json.load(urllib.request.urlopen('http://172.19.5.246:11435/api/ps'))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 report['samples']+=list(pool.map(lambda i:bench.measure('gemma4-12b','long','concurrent-'+str(i)),range(2)))
report['samples'].append(bench.measure('fast','short','reload-after-first-initialization'))
report['residency_fast']=json.load(urllib.request.urlopen('http://172.19.5.246:11435/api/ps'))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 report['samples']+=list(pool.map(lambda i:bench.measure('fast','short','concurrent-'+str(i)),range(2)))
status,value,elapsed=call({'model':'fast','messages':[{'role':'user','content':'Texto fictício: a equipe Alfa tem prazo de cinco dias úteis. Responda somente o prazo, sem explicação.'}],'max_tokens':80,'temperature':0})
answer=value.get('choices',[{}])[0].get('message',{}).get('content','')
report['checks']['short_factual_answer']=status==200 and ('cinco' in answer.lower() or '5' in answer)
report['quality_answer']={'status':status,'elapsed_seconds':elapsed,'answer':answer}
report['checks']['concurrent_streams_completed']=all(s.get('status')==200 and s.get('stream_done') and s.get('moara',{}).get('inference_used') for s in report['samples'])
report['checks']['gemma_fully_in_vram']=all(m.get('size_vram',0)==m.get('size',-1) for m in report['residency_gemma'].get('models',[]))
report['checks']['fast_fully_in_vram']=all(m.get('size_vram',0)==m.get('size',-1) for m in report['residency_fast'].get('models',[]))
path=bench.ROOT/'docs/runtime/gpu-validation-extra.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'checks':report['checks'],'quality_answer':report['quality_answer'],'file':str(path)},ensure_ascii=False),flush=True)
