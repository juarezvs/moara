"""Real browser, authenticated portal APIs and model-driven file operations."""
import sys,json,hashlib
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline());checks={};resources=[];errors=[];session=None
output=Path('/artifacts/unified-ui.json')
def checkpoint(context):
 cookie=next((c['value'] for c in context.cookies() if c['name']=='__Secure-moara_session'),None)
 output.write_text(json.dumps({'checks':checks,'created_resources':resources,'test_session_sha256':hashlib.sha256(cookie.encode()).hexdigest() if cookie else None,'javascript_errors':errors}))
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']])
 context=browser.new_context(viewport={'width':1500,'height':1100},timezone_id='America/Manaus')
 if fixture.get('proxy'):
  def proxy(route):
   u=urlsplit(route.request.url)
   response=route.fetch(url='http://'+fixture['proxy']+':8080'+u.path+('?' +u.query if u.query else ''),max_redirects=0,timeout=600000)
   route.fulfill(response=response)
  context.route('https://moara.am.trf1.gov.br/**',proxy)
 context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:160]))
 def api(method,path,body=None):
  return page.evaluate("""async({method,path,body})=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();const r=await fetch('/moara/api/v1/'+path,{method,headers:{'Content-Type':'application/json','X-Moara-CSRF':me.csrf_token},...(body===null?{}:{body:JSON.stringify(body)})});return {status:r.status,value:await r.json()};}""",{'method':method,'path':path,'body':body})
 try:
  page.goto('https://moara.am.trf1.gov.br/moara/',wait_until='domcontentloaded')
  expect(page.locator('.dashboard-cards')).to_be_visible(timeout=45000);checkpoint(context)
  r=api('POST','platform/resources',{'kind':'project','title':'Arquivos QA '+str(__import__('time').time_ns()),'body':{'language':'python','description':'Projeto pessoal de validacao de arquivos','files':{'main.py':'print("QA")'}}})
  assert r['status']==201,r;identifier=r['value']['id'];resources.append(identifier);checkpoint(context)
  path='platform/projects/'+identifier
  tree=api('GET',path+'/files')['value'];checks['owned_project_files_listed']=tree['files'][0]['path']=='main.py'
  sha=tree['files'][0]['sha256']
  r=api('POST',path+'/files',{'version':1,'operations':[{'op':'write','path':'main.py','content':'print("CHANGED")','expected_sha256':sha},{'op':'mkdir','path':'empty/nested'}]})
  assert r['status']==200,r
  stale=api('POST',path+'/files',{'version':1,'operations':[{'op':'delete','path':'main.py'}]})
  checks['stale_changes_are_rejected']=stale['status']==409
  current=api('GET','platform/resources/'+identifier)['value']
  version=current['version']
  bad=api('POST',path+'/files',{'version':version,'operations':[{'op':'write','path':'second.py','content':'safe'},{'op':'mkdir','path':'../escape'}]})
  checks['unsafe_batch_is_rejected']=bad['status']==422
  checks['failed_batch_is_atomic']='second.py' not in api('GET','platform/resources/'+identifier)['value']['body']['files']
  page.goto('https://moara.am.trf1.gov.br/moara/espaco',wait_until='domcontentloaded')
  page.get_by_role('button',name='MOARA DEV',exact=True).click()
  page.get_by_role('button',name=current['title'],exact=True).click()
  expect(page.get_by_label('Nova pasta',exact=True)).to_be_visible()
  checks['folder_browser_visible']=page.get_by_role('button',name='▱ empty/nested/',exact=True).is_visible()
  page.get_by_label('Nova pasta',exact=True).fill('docs')
  page.get_by_role('button',name='Criar pasta',exact=True).click()
  expect(page.get_by_role('button',name='▱ docs/',exact=True)).to_be_visible(timeout=30000)
  checks['create_folder_in_ui']=True
  page.get_by_label('Caminho selecionado',exact=True).fill('docs')
  page.get_by_label('Novo nome ou destino',exact=True).fill('documentation')
  page.get_by_role('button',name='Renomear ou mover',exact=True).click()
  expect(page.get_by_role('button',name='▱ documentation/',exact=True)).to_be_visible(timeout=30000)
  checks['move_folder_in_ui']=True
  page.get_by_label('Caminho selecionado',exact=True).fill('documentation')
  page.get_by_role('button',name='Excluir',exact=True).click()
  page.get_by_role('button',name='Confirmar exclusão',exact=True).click()
  expect(page.get_by_role('button',name='▱ documentation/',exact=True)).to_have_count(0,timeout=30000)
  checks['delete_folder_in_ui']=True
  page.get_by_label('Solicitação',exact=True).fill('Crie a pasta src e o arquivo src/calculo.py contendo apenas def dobro(n): return n * 2. Use project_write para salvar o arquivo. Preserve main.py. Nao execute comandos nem acrescente outros arquivos.')
  with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/assistant'),timeout=540000) as task:
   page.get_by_role('button',name='Aplicar solicitação aos arquivos',exact=True).click()
  assert task.value.status==200,task.value.text()
  expect(page.get_by_role('button',name='▤ src/calculo.py',exact=True)).to_be_visible(timeout=540000)
  current=api('GET','platform/resources/'+identifier)['value'];files=current['body']['files']
  checks['ai_created_real_file']='src/calculo.py' in files and 'def dobro' in files['src/calculo.py']
  checks['ai_preserved_existing_file']=files.get('main.py')=='print("CHANGED")'
  page.get_by_label('Solicitação',exact=True).fill('Leia src/calculo.py e altere a funcao dobro para retornar n * 3. Use o sha256 obtido na leitura para replace ou write. Depois mova src/calculo.py para src/triplo.py. Preserve main.py. Use project_read, project_write e project_move, sem executar comandos nem criar outros arquivos.')
  with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/assistant'),timeout=540000) as task:
   page.get_by_role('button',name='Aplicar solicitação aos arquivos',exact=True).click()
  assert task.value.status==200,task.value.text()
  expect(page.get_by_role('button',name='▤ src/triplo.py',exact=True)).to_be_visible(timeout=540000)
  current=api('GET','platform/resources/'+identifier)['value'];files=current['body']['files']
  checks['ai_read_edited_and_moved_existing_file']='src/triplo.py' in files and 'src/calculo.py' not in files and '*3' in files['src/triplo.py'].replace(' ','')
  checks['ai_edit_preserved_other_files']=files.get('main.py')=='print("CHANGED")'
  page.get_by_label('Restaurar arquivos de uma versão',exact=True).fill('1')
  page.get_by_role('button',name='Restaurar como nova versão',exact=True).click()
  expect(page.get_by_role('button',name='▤ src/triplo.py',exact=True)).to_have_count(0,timeout=30000)
  restored=api('GET','platform/resources/'+identifier)['value']
  checks['restore_keeps_history_and_increments_version']=restored['version']>current['version'] and restored['body']['files']=={'main.py':'print("QA")'}
  versions=api('GET','platform/resources/'+identifier+'/versions')['value']
  checks['history_preserves_intermediate_versions']=len(versions)>=8
  page.screenshot(path='/artifacts/project-files-desktop.png',mask=[page.locator('.sidebar')])
  page.set_viewport_size({'width':390,'height':844})
  checks['mobile_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
  checks['no_javascript_errors']=not errors
 finally:
  try:
   for identifier in resources:
    row=api('GET','platform/resources/'+identifier)['value']
    archived=api('POST','platform/resources/'+identifier+'/archive',{'version':row['version']})
    checks['synthetic_project_archived']=archived['status']==200
  finally:checkpoint(context);context.close();browser.close()
print(json.dumps({'checks':checks}));assert checks and all(checks.values()),checks
