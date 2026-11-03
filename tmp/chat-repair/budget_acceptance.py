import pathlib,subprocess,importlib.util,json
root=pathlib.Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import sys,json,urllib.request
token=sys.stdin.read().strip()
current='### Task:\n<context><source id="1">Documento inteiramente fictício. O prazo interno informado é de nove dias úteis.</source></context>\n<moara_user_query>Resuma o prazo informado no documento, sem acrescentar fatos.</moara_user_query>'
messages=[{'role':'user','content':'Conversa antiga de teste sem vínculo com o documento atual. '*500},
 {'role':'assistant','content':'Resposta anterior sintética sem conteúdo processual. '*400},
 {'role':'user','content':current}]
request=urllib.request.Request('http://localhost:8075/v1/chat/completions',data=json.dumps({'model':'auto','messages':messages,'max_tokens':128}).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=120) as r:value=json.load(r)
meta=value['moara'];text=value['choices'][0]['message']['content']
assert meta['context_management']['omitted_messages']==2
assert meta['context_management']['current_input_truncated'] is False
assert '2 mensagens anteriores ficaram fora do contexto' in text
assert meta['execution_backend']=='gpu' and meta['citation_validation']=='client_source_ids_only'
assert '[1]' in text and ('nove' in text or '9' in text)
print(json.dumps({'passed':True,'notice_in_answer':True,'metadata':meta}))
'''
p=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session(),capture_output=True,text=True,timeout=180)
if p.returncode:raise RuntimeError(p.stderr[-1400:])
(root/'docs/runtime/chat-repair-budget-acceptance.json').write_text(p.stdout);print(p.stdout)
