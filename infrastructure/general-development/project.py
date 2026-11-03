"""Actual authorized personal project generation and existing isolated execution."""
import pathlib,subprocess,json,importlib.util
root=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import sys,json,time,httpx,uuid
token=sys.stdin.read().strip();checks={};project=None;execution=None;generation=None
with httpx.Client(base_url='http://localhost:8075/api/v1/',headers={'Authorization':'Bearer '+token},trust_env=False,timeout=30) as c:
 def request(method,path,**kwargs):
  r=c.request(method,path,**kwargs);r.raise_for_status();return r.json()
 def wait(identifier):
  start=time.monotonic()
  while time.monotonic()-start<240:
   row=request('GET','platform/runs/'+identifier)
   if row['status'] in ('completed','failed','cancelled'):return row
   time.sleep(2)
  raise RuntimeError('Synthetic project deadline exceeded')
 try:
  project=request('POST','platform/resources',json={'kind':'project','title':'General development QA '+str(uuid.uuid4()),'body':{'language':'python','description':'Aplicativo pessoal para minha loja de bolos, sem vínculo institucional. Gere main.py em Python usando apenas biblioteca padrão. Implemente total(precos,quantidades), que soma preco*quantidade, rejeita quantidade negativa com ValueError. Quando main.py for executado, rode asserts total([10,2.5],[2,3])==27.5 e total([],[])==0, e ao terminar imprima somente DEMO_OK. Não use input(), servidor HTTP ou dependências externas.','files':{}}})
  generation=request('POST','platform/runs',json={'operation':'project.generate','resource_id':project['id'],'input':{}})
  row=wait(generation['id']);checks['personal_project_generated']=row['status']=='completed'
  assert checks['personal_project_generated'],row.get('error_code')
  proposal=row['result'];checks['project_contains_real_source']='main.py' in proposal['files']
  checks['generation_does_not_fake_execution']=proposal.get('executed') is False
  accepted=request('POST','platform/projects/'+project['id']+'/accept',json={'version':proposal['project_version'],'digest':proposal['digest'],'run_id':generation['id']})
  review=request('GET','platform/projects/'+project['id']+'/review')
  checks['existing_sandbox_is_enabled']=review['execution_enabled'] is True
  execution=request('POST','platform/projects/'+project['id']+'/execute',json={'version':review['version'],'digest':review['digest']})
  result=wait(execution['id']);checks['project_execution_completed']=result['status']=='completed'
  outcome=result.get('result') or {}
  checks['generated_application_tests_pass']=outcome.get('exit_code')==0 and outcome.get('output','').strip()=='DEMO_OK'
  checks['execution_stays_isolated']=outcome.get('network')=='none'
  print(json.dumps({'checks':checks,'generation_id':generation['id'],'execution_id':execution['id'],'result':outcome,'files':proposal['files']},ensure_ascii=True))
 finally:
  if project:
   latest=request('GET','platform/resources/'+project['id'])
   request('POST','platform/resources/'+project['id']+'/archive',json={'version':latest['version']})
'''
r=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session(),capture_output=True,text=True,timeout=600)
if r.returncode:raise RuntimeError('Project validation failed: '+r.stderr[-1000:])
report=json.loads(r.stdout);report['tested_image_id']=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
(root/'docs/runtime/general-development-project.json').write_text(json.dumps(report,indent=2,ensure_ascii=True));print(json.dumps(report['checks']));assert all(report['checks'].values())
