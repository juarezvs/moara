import pathlib,subprocess,importlib.util,json,sys
root=pathlib.Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import json,sys,urllib.request,time
token=sys.stdin.read().strip();messages=[];report=[]
def send(question,path='/v1/chat/completions',stream=False):
 messages.append({'role':'user','content':question});started=time.monotonic()
 request=urllib.request.Request('http://localhost:8075'+path,data=json.dumps({'model':'auto','messages':messages,'max_tokens':128,'stream':stream}).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=150) as response:raw=response.read().decode()
 if stream:
  chunks=[json.loads(line[6:]) for line in raw.splitlines() if line.startswith('data: ') and line[6:]!='[DONE]']
  answer=''.join(c.get('delta',{}).get('content','') for row in chunks for c in row.get('choices',[]))
  metadata=next(row['moara'] for row in chunks if 'moara' in row)
  assert '[DONE]' in raw
 else:
  value=json.loads(raw);answer=value['choices'][0]['message']['content'];metadata=value['moara']
 messages.append({'role':'assistant','content':answer})
 report.append({'question':question,'answer_excerpt':answer[:400],'metadata':metadata,'seconds':round(time.monotonic()-started,2),'stream':stream})
 return answer,metadata
send('Oi')
for text in ['quais suas habilidades?','o que você pode fazer?']:
 answer,meta=send(text,stream=True)
 assert 'seis especialidades' in answer and meta['reason']=='institutional_identity' and not meta['inference_used']
 assert 'legal_verification' not in meta
answer,meta=send('me explique o art. 6º da lei 14133/2021')
assert '14.133/2021, art. 6' in answer and 'data atual ou uma data específica' in answer
answer,meta=send('hoje',stream=True)
legal=meta['legal_verification'];assert legal['status']!='clarification_required' and legal['legal_conclusion_allowed'] is False
assert legal.get('evidence_id') and legal.get('reference_date')
evidence=urllib.request.Request('http://localhost:8075/api/v1/legal/evidence/'+legal['evidence_id'],headers={'Authorization':'Bearer '+token})
with urllib.request.urlopen(evidence,timeout=20) as response:saved=json.load(response)
assert saved['verification']['norms'][0]['norm']['number']==14133
assert saved['verification']['norms'][0]['norm']['articles']==['6']
answer,meta=send('o que você pode fazer?',path='/api/v1/chat/completions')
assert meta['reason']=='institutional_identity' and 'legal_verification' not in meta
answer,meta=send('Qual é o significado de uma API?',path='/api/v1/chat/completions')
assert meta['inference_used'] and meta.get('execution_backend')=='gpu'
print(json.dumps({'checks_passed':True,'sequence':report,'evidence_replayed':True}))
'''
container=sys.argv[1] if len(sys.argv)>1 else (root/'tmp/chat-intent-stage-name.txt').read_text().strip()
phase=sys.argv[2] if len(sys.argv)>2 else 'stage'
p=subprocess.run(['docker','exec','-i',container,'python','-c',code],input=m.admin_session(),capture_output=True,text=True,timeout=400)
if p.returncode:raise RuntimeError(p.stderr[-2300:])
(root/'docs/runtime'/('chat-repair-acceptance-'+phase+'.json')).write_text(p.stdout)
print(p.stdout)
