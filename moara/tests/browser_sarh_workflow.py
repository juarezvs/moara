"""Real administrative catalog and AI workflow through the published TLS site."""
import os,json,subprocess,sys,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
fixture=json.load(sys.stdin);home=Path('/tmp/qa-home');nss=home/'.pki/nssdb';nss.mkdir(parents=True)
(home/'root.crt').write_text(fixture['ca_pem'])
subprocess.run(['certutil','-N','--empty-password','-d','sql:'+str(nss)],check=True,capture_output=True)
subprocess.run(['certutil','-A','-d','sql:'+str(nss),'-n','Moara','-t','C,,','-i',str(home/'root.crt')],check=True,capture_output=True)
out=Path('/tmp/sarh-workflow');out.mkdir();checks={};errors=[]
origin='https://moara.am.trf1.gov.br';chat_id=None
with sync_playwright() as p:
 b=p.chromium.launch(chromium_sandbox=True,env={**os.environ,'HOME':str(home)})
 context=b.new_context(viewport={'width':1440,'height':1000},locale='pt-BR')
 context.add_init_script('localStorage.setItem("token",'+json.dumps(fixture['token'])+');')
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:160]))
 try:
  page.goto(origin+'/moara/fontes?tecnologia=oracle&origem=secp')
  rows=page.locator('#source-registry tbody tr');expect(rows).to_have_count(9,timeout=45000)
  checks['nine_registrations_visible']=True
  rows.filter(has=page.get_by_text('SJAM - Oracle SARH',exact=True)).get_by_role('button',name='Detalhes').click()
  detail=page.locator('.source-detail');expect(detail.locator('h2')).to_have_text('SJAM - Oracle SARH')
  detail.get_by_role('button',name='Conexão',exact=True).click();expect(detail).to_contain_text('TRF_SARH_SERVIDOR');checks['registration_connection_details_visible']=True
  detail.get_by_role('button',name='Catálogo e acesso da IA',exact=True).click()
  catalog=page.locator('moara-source-catalog');expect(catalog).to_contain_text('275 objetos descobertos')
  checks['full_discovered_catalog_visible']=catalog.locator('tbody tr').count()==275
  catalog.locator('[name=catalogSearch]').fill('SARH.SERV_PESSOAL')
  object_row=catalog.locator('tbody tr').first;expect(object_row.get_by_role('checkbox')).to_be_checked()
  object_row.get_by_role('button',name='Escolher campos').click()
  cpf=catalog.get_by_role('checkbox',name='CPF_SERVIDOR',exact=False);expect(cpf).to_be_disabled();expect(cpf).not_to_be_checked()
  checks['sensitive_field_not_silently_released']=True
  catalog.screenshot(path=str(out/'catalog-fields.png'))
  # Save the same scope via the real administrative form; no permission added.
  catalog.get_by_role('button',name='Salvar acesso da IA a tabelas e campos').click()
  expect(catalog.get_by_role('button',name='Salvar acesso da IA a tabelas e campos')).to_be_enabled(timeout=45000)
  expect(catalog).to_contain_text('8 selecionados');checks['catalog_save_revalidates_successfully']=True
  detail.get_by_role('button',name='Visão geral',exact=True).click()
  detail.get_by_role('button',name='Perguntar à IA sobre esta fonte').click()
  expect(page.locator('[name=questionSource]')).to_have_value('4f41d378-e67d-4b29-a3f3-6c5bb8f3d016')
  options=page.locator('[name=questionSource] option').all_text_contents();checks['only_seven_active_sources_selectable']=len(options)==8 and not any('SJPI' in s or 'JFAM' in s for s in options)
  page.locator('[name=question]').fill('Quantos registros existem na tabela SARH.SERV_PESSOAL?')
  page.get_by_role('button',name='Planejar e consultar',exact=True).click()
  answer=page.locator('.answer-box');expect(answer).to_contain_text('registros',timeout=45000);expect(answer).to_contain_text('SJAM - Oracle SARH')
  checks['selected_source_real_ai_answer']=True;page.screenshot(path=str(out/'assisted-answer.png'))
  # Native chat must also read the database, rather than only display API data.
  page.goto(origin+'/');page.locator('#chat-input').wait_for(timeout=60000)
  page.locator('#model-selector-model-button').first.click();page.get_by_text('Moara AI · Automático',exact=True).first.click()
  page.locator('#chat-input').fill('Na fonte SJAM - Oracle SARH, quantos registros existem na tabela SARH.RH_CARGO? Consulte o banco de dados e informe o total com a fonte.')
  page.locator('#send-message-button').click();page.wait_for_url('**/c/**',timeout=30000);chat_id=page.url.rsplit('/',1)[-1]
  print(json.dumps({'phase':'native_chat_started','chat_id':chat_id}),flush=True)
  # Wait for actual backend-tool evidence. Never accept a guessed model number.
  for n in range(180):
   content=page.locator('#chat-container').inner_text()
   if '342' in content and ('SJAM' in content or 'RH_CARGO' in content) and page.locator('#stop-response-button').count()==0:break
   page.wait_for_timeout(2000)
  checks['native_chat_real_answer']='342' in page.locator('#chat-container').inner_text()
  page.screenshot(path=str(out/'native-data-answer.png'),full_page=True)
  print(json.dumps({'phase':'native_chat_finished','passed':checks['native_chat_real_answer']}),flush=True)
  page.goto(origin+'/moara/fontes?tecnologia=oracle&origem=secp');expect(page.locator('#source-registry tbody tr')).to_have_count(9)
  page.set_viewport_size({'width':390,'height':844});checks['mobile_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  page.screenshot(path=str(out/'mobile.png'),full_page=True)
 finally:
  if chat_id:
   response=page.evaluate("async id=>(await fetch('/api/v1/chats/'+encodeURIComponent(id),{method:'DELETE',headers:{Authorization:'Bearer '+localStorage.getItem('token')}})).status",chat_id)
   checks['only_synthetic_chat_removed']=response==200
  context.close();b.close()
report={'passed':all(checks.values()) and not errors,'checks':checks,'page_errors':errors,'scope':'Actual published catalog editor, bounded AI data query and native chat; no Oracle writes or new users/groups'}
(out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
