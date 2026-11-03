import pathlib,subprocess,json,sys,importlib.util,hashlib,shutil
root=pathlib.Path(__file__).resolve().parents[2];stage='--stage' in sys.argv
core=json.loads((root/'tmp/general-development-stage.json').read_text())['core'] if stage else 'ai-server-moara-gateway-1'
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
token=m.admin_session();checks={};reports=[]
def request(body):
 code="""import sys,json,httpx
d=json.load(sys.stdin)
with httpx.Client(trust_env=False,timeout=240) as c:
 r=c.post('http://localhost:8075/v1/chat/completions',headers={'Authorization':'Bearer '+d['token']},json=d['body']);r.raise_for_status();print(r.text)
"""
 r=subprocess.run(['docker','exec','-i',core,'python','-c',code],input=json.dumps({'token':token,'body':body}),capture_output=True,text=True,timeout=260)
 if r.returncode:raise RuntimeError('Development request failed: '+r.stderr[-700:])
 if not body.get('stream'):return json.loads(r.stdout)
 text='';metadata={}
 for line in r.stdout.splitlines():
  if not line.startswith('data: ') or line=='data: [DONE]':continue
  chunk=json.loads(line[6:]);metadata=chunk.get('moara',metadata)
  for choice in chunk.get('choices',[]):text+=choice.get('delta',{}).get('content') or ''
 return {'choices':[{'message':{'role':'assistant','content':text}}],'moara':metadata}
def scoped(value):
 return value.get('moara',{}).get('assistant',{}).get('development_scope')=='general_software' and value['moara'].get('inference_used') is True
q='Crie um site pessoal de receitas de bolo, sem relação com a instituição. Use um único HTML simples, sem bibliotecas externas. Entregue o código com um título, duas receitas e botão que altera o tema. Não peça justificativa institucional.'
value=request({'model':'auto','messages':[{'role':'user','content':q}],'max_tokens':900})
checks['automatic_personal_recipe_site_is_development']=scoped(value)
checks['automatic_request_generates_code']='<html' in (value['choices'][0]['message'].get('content') or '').lower() or '<!doctype' in (value['choices'][0]['message'].get('content') or '').lower()
reports.append({'case':'automatic_personal_website','response':value})
folder=root/'tmp'/('general-development-demo-stage' if stage else 'general-development-demo-public');folder.mkdir(exist_ok=True)
shutil.copyfile(root/'infrastructure/general-development/play.py',folder/'play.py')
renderer=json.loads(subprocess.check_output(['docker','inspect','ai-server-studio-renderer-1']))[0]
tool={'type':'function','function':{'name':'write_file','description':'Grava um arquivo no projeto local de teste autorizado.','parameters':{'type':'object','properties':{'path':{'type':'string','enum':['index.html']},'content':{'type':'string'}},'required':['path','content'],'additionalProperties':False}}}
question='Desenvolva um jogo da velha completo para entretenimento pessoal, sem relação com a Justiça. Use apenas index.html, com CSS e JavaScript internos, sem dependências externas. Dois jogadores locais, X começa. Use exatamente nove buttons com data-cell de 0 a 8, #status que informa de quem é a vez e mostra "X venceu" ou "O venceu" ao terminar, e button #reset para recomeçar limpando as células. Impeça jogadas depois da vitória. O layout deve funcionar em celular. Implemente o arquivo usando write_file, sem introdu??o em texto. Escreva uma implementa??o completa e enxuta, com no m?ximo 6000 caracteres, sem anima??es nem recursos extras.'
messages=[{'role':'user','content':question}]
for attempt in range(3):
 value=request({'model':'moara-code','messages':messages,'tools':[tool],'parallel_tool_calls':False,'tool_choice':{'type':'function','function':{'name':'write_file'}},'max_tokens':4096})
 message=value['choices'][0]['message'];calls=message.get('tool_calls') or []
 checks['ide_general_development_scope']=scoped(value)
 checks['ide_returns_real_tool_call']=bool(calls) and calls[0].get('function',{}).get('name')=='write_file'
 if not calls:reports.append({'case':'ide_missing_tool','response':value});break
 try:
  args=json.loads(calls[0]['function']['arguments'])
  assert isinstance(args,dict) and args.get('path')=='index.html' and isinstance(args.get('content'),str) and len(args['content'])<200000
 except (ValueError,TypeError,AssertionError):
  reports.append({'case':'tool_argument_validation_error','attempt':attempt+1,'response':value})
  messages.append({k:v for k,v in message.items() if k in ('role','content','tool_calls')})
  for call in calls:messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps({'error':'invalid_arguments','required_fields':{'path':'index.html','content':'complete HTML string'},'written':False})})
  messages.append({'role':'user','content':'Corrija a chamada de write_file: os argumentos devem ter exatamente path e content, conforme o contrato da ferramenta. Não use outros nomes de campos. Envie o HTML completo em content.'})
  continue
 checks['ide_valid_tool_arguments']=True
 (folder/'index.html').write_text(args['content'],encoding='utf8')
 argv=['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=512m,mode=1777','--shm-size','256m','--memory','1g','--cpus','2','-e','HOME=/tmp','-v',str(folder)+':/tests:ro']
 cfg=json.loads(subprocess.check_output(['sh',str(root/'moara/infrastructure/scripts/compose.sh'),'config','--format','json']))
 for option in cfg['services']['studio-renderer'].get('security_opt',[]):
  if option.startswith('seccomp=') and not option.startswith('seccomp=/'):option='seccomp='+str((root/'infrastructure'/option.split('=',1)[1]).resolve())
  argv+=['--security-opt',option]
 argv+=['--entrypoint','python3',renderer['Image'],'/tests/play.py']
 r=subprocess.run(argv,capture_output=True,text=True,timeout=100)
 reports.append({'case':'generated_personal_game','attempt':attempt+1,'response':value,'browser_passed':r.returncode==0,'browser_error':r.stderr[-1200:] if r.returncode else None})
 messages.append({k:v for k,v in message.items() if k in ('role','content','tool_calls')})
 for call in calls:
  messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps({'path':'index.html','written':True,'browser_tests_passed':r.returncode==0,'test_feedback':r.stdout[-1000:] if not r.returncode else r.stderr[-1000:]})})
 if not r.returncode:
  browser_checks=json.loads(r.stdout);checks.update({'game_'+k:v for k,v in browser_checks.items()})
  checks['generated_file_written_and_tested']=True
  summary=request({'model':'moara-code','messages':messages,'tools':[tool],'tool_choice':'none','max_tokens':160,'stream':True})
  checks['ide_tool_result_and_streaming_continue']=bool(summary['choices'][0]['message']['content']) and scoped(summary)
  reports.append({'case':'agent_tool_result_stream','response':summary})
  break
 messages.append({'role':'user','content':'Corrija index.html para passar os testes informados. Regrave o arquivo completo usando write_file.'})
else:checks['generated_file_written_and_tested']=False
if 'generated_file_written_and_tested' not in checks:checks['generated_file_written_and_tested']=False
image=subprocess.check_output(['docker','inspect',core,'--format','{{.Image}}'],text=True).strip()
report={'checks':checks,'reports':reports,'tested_image_id':image}
(root/'docs/runtime'/('general-development-stage.json' if stage else 'general-development-public.json')).write_text(json.dumps(report,indent=2,ensure_ascii=True))
print(json.dumps({'checks':checks,'image':image}));assert all(checks.values())
