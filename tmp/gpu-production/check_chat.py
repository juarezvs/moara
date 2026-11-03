import sys,pathlib,json,ssl,time,urllib.request,importlib.util
ROOT=pathlib.Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
token=m.admin_session()
mode=sys.argv[1];expected=sys.argv[2]
base='http://127.0.0.1:18075' if mode=='stage' else 'https://localhost:8443/moara'
tls=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/ai-root-ca.crt'))
body={'model':'gemma4-12b' if mode=='stage' else 'auto','messages':[{'role':'user','content':'Texto fictício: o prazo da equipe Alfa é de cinco dias úteis. Responda somente qual é o prazo.'}],'max_tokens':64,'temperature':0}
request=urllib.request.Request(base+'/api/v1/chat/completions',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
start=time.monotonic()
with urllib.request.urlopen(request,context=tls,timeout=180) as r:
 d=json.load(r);report={'mode':mode,'status':r.status,'seconds':time.monotonic()-start,'moara':d.get('moara'),'answer':d['choices'][0]['message']['content']}
print(json.dumps(report,ensure_ascii=False),flush=True)
assert report['moara']['execution_backend']==expected,report
assert 'cinco' in report['answer'].lower() or '5' in report['answer'],report
