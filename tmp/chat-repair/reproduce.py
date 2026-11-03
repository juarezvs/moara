import pathlib,subprocess,importlib.util,json,sys
root=pathlib.Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import json,sys,urllib.request,time
token=sys.stdin.read().strip();messages=[];report=[]
for question in ['Oi','quais suas habilidades?','o que você pode fazer?','me explique o art. 6º da lei 14133/2021']:
 messages.append({'role':'user','content':question});started=time.monotonic()
 request=urllib.request.Request('http://localhost:8075/v1/chat/completions',data=json.dumps({'model':'auto','messages':messages,'max_tokens':96}).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=120) as response:value=json.load(response)
 answer=value['choices'][0]['message']['content'];messages.append({'role':'assistant','content':answer})
 report.append({'question':question,'answer':answer[:450],'metadata':value['moara'],'seconds':round(time.monotonic()-started,2)})
print(json.dumps(report))
'''
container=sys.argv[1] if len(sys.argv)>1 else 'ai-server-moara-gateway-1'
p=subprocess.run(['docker','exec','-i',container,'python','-c',code],input=m.admin_session(),capture_output=True,text=True,timeout=240)
if p.returncode:raise RuntimeError(p.stderr[-1600:])
phase=sys.argv[2] if len(sys.argv)>2 else 'before'
(root/'docs/runtime'/('chat-repair-'+phase+'.json')).write_text(p.stdout)
print(p.stdout)
