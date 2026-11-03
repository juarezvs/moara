"""Real portal, owner-isolated prior history, contextual controls and public routes."""
import sys,json,hashlib,re
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline());checks={};chats=[];resources=[];errors=[];rbac_accounts=[]
output=Path('/artifacts/unified-ui.json')
def configure(context):
 if fixture.get('proxy'):
  def proxy(route):
   u=urlsplit(route.request.url)
   try:response=route.fetch(url='http://'+fixture['proxy']+':8080'+u.path+('?' +u.query if u.query else ''),max_redirects=0,timeout=180000)
   except Exception:raise RuntimeError('Candidate proxy request failed; sensitive headers suppressed') from None
   route.fulfill(response=response)
  context.route('https://moara.am.trf1.gov.br/**',proxy)
def checkpoint(context):
 cookie=next((c['value'] for c in context.cookies() if c['name']=='__Secure-moara_session'),None)
 output.write_text(json.dumps({'checks':checks,'created_chats':chats,'created_resources':resources,'created_rbac_accounts':rbac_accounts,'test_session_sha256':hashlib.sha256(cookie.encode()).hexdigest() if cookie else None,'javascript_errors':errors}))
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']])
 anon=browser.new_context(viewport={'width':1400,'height':1000});configure(anon);login=anon.new_page()
 login.goto('https://moara.am.trf1.gov.br/'+('moara/login' if fixture.get('proxy') else '?interface=anterior'),wait_until='domcontentloaded')
 expect(login.get_by_role('heading',name='Entre na Moara')).to_be_visible(timeout=45000)
 checks['native_anonymous_login']='/moara/login' in login.url and login.locator('a[href*="interface=anterior"]').count()==0
 expect(login.locator('input[name=email]')).to_have_attribute('type','text');checks['native_login_accepts_directory_identifier']=True
 expect(login.locator('select[name=organization]')).to_have_value('sjam',timeout=20000)
 checks['login_field_order']=login.locator('form input[name=email],form input[name=password],form select[name=organization]').evaluate_all("els=>els.map(e=>e.name)")==['email','password','organization']
 checks['official_directory_catalog_loaded']=login.locator('select[name=organization] option[value=sjam]').count()==1
 login.set_viewport_size({'width':390,'height':844});login.screenshot(path='/artifacts/login-mobile.png',full_page=True)
 checks['login_mobile_no_overflow']=login.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 login.set_viewport_size({'width':1400,'height':1000});login.screenshot(path='/artifacts/login-desktop.png',full_page=True)
 captured=[]
 def network_login(route):
  captured.append(route.request.post_data_json)
  route.fulfill(status=200,content_type='application/json',body=json.dumps({'mfa_required':True,'next_step':'verify','challenge_token':'SYNTHETIC_CHALLENGE_FOR_UI_TEST_00000'}))
 login.route('**/moara/api/v1/auth/login',network_login)
 login.locator('input[name=email]').fill('qa1234');login.locator('input[name=password]').fill('SYNTHETIC_PASSWORD')
 login.get_by_role('button',name=re.compile('^Entrar')).click()
 expect(login.locator('input[name=mfa-code]')).to_be_visible()
 checks['selected_organization_routes_network_credentials']=captured==[{'email':'sjam'+chr(92)+'qa1234','password':'SYNTHETIC_PASSWORD'}]
 login.get_by_role('button',name='Reiniciar acesso').click()
 # An isolated browser-only challenge verifies the new UI; it grants no server session.
 login.route('**/moara/api/v1/auth/login',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps({'mfa_required':True,'next_step':'verify','challenge_token':'SYNTHETIC_CHALLENGE_FOR_UI_TEST_00000'})))
 login.locator('select[name=organization]').select_option('local');login.locator('input[name=email]').fill('synthetic@example.test');login.locator('input[name=password]').fill('SYNTHETIC_PASSWORD')
 login.get_by_role('button',name=re.compile('^Entrar')).click();expect(login.get_by_role('heading',name='Verificação adicional')).to_be_visible()
 checks['mfa_stays_in_native_interface']=login.locator('input[name=mfa-code]').count()==1
 login.get_by_role('button',name='Reiniciar acesso').click();expect(login.locator('input[name=password]')).to_have_value('');anon.close()
 context=browser.new_context(viewport={'width':1600,'height':1100},has_touch=True);configure(context)
 context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:160]))
 def seen(r):
  if r.request.method=='POST' and r.status==201:
   if r.url.endswith('/moara/api/v1/chats') or re.search('/history/previous/[^/]+/resume$',r.url):chats.append(r.json()['id']);checkpoint(context)
   if r.url.endswith('/moara/api/v1/platform/documents'):resources.append(r.json()['id']);checkpoint(context)
 page.on('response',seen)
 try:
  page.goto('https://moara.am.trf1.gov.br/'+('moara/chat' if fixture.get('proxy') else ''),wait_until='domcontentloaded')
  expect(page.get_by_role('heading',name='Como posso ajudar você hoje?')).to_be_visible(timeout=45000);checkpoint(context)
  checks['current_chat_loads']='/moara/chat' in page.url
  expect(page.locator('.moara-site-header .header-brand')).to_contain_text('Moara');expect(page.locator('.moara-site-header')).to_contain_text('Justiça Federal do Amazonas')
  checks['header_uses_original_brand']=page.locator('.header-brand img').get_attribute('src')=='brand/mark.svg'
  checks['no_legacy_chat_links']=page.locator('a[href*="interface=anterior"],a[href*="chat-anterior"]').count()==0
  context_button=page.get_by_role('button',name='Contexto',exact=True);options=page.get_by_role('button',name='Opções',exact=True)
  expect(context_button).to_have_attribute('aria-expanded','false');expect(page.locator('#work-context')).to_have_count(0)
  page.get_by_label('Sua mensagem',exact=True).fill('Rascunho sintético que deve ser preservado ao abrir o contexto.')
  context_button.click();expect(page.get_by_role('region',name='Contexto de trabalho')).to_be_visible();expect(page.locator('.context-row')).to_have_count(5)
  a=options.bounding_box();b=context_button.bounding_box();checks['context_beside_options']=abs(a['y']-b['y'])<2 and b['x']>a['x']
  checks['context_uses_layers_icon']=context_button.locator('svg path').get_attribute('d').startswith('m12 3')
  context_button.focus();page.keyboard.press('Enter');expect(context_button).to_have_attribute('aria-expanded','false')
  expect(page.get_by_label('Sua mensagem',exact=True)).to_have_value('Rascunho sintético que deve ser preservado ao abrir o contexto.');checks['keyboard_toggle_preserves_draft']=True
  options.click();expect(page.locator('#work-settings')).to_be_visible();context_button.click();context_button.click();expect(page.locator('#work-settings')).to_be_visible();options.click();checks['context_independent_of_options']=True
  page.screenshot(path='/artifacts/unified-desktop.png',mask=[page.locator('.history-items'),page.locator('.work-user')],mask_color='#0b142b')
  context_button.click();page.get_by_role('button',name=re.compile('^Documentos Arquivos')).click()
  page.locator('input[type=file]').first.set_input_files({'name':'moara-contexto-sintetico.txt','mimeType':'text/plain','buffer':b'Test fixture only. The synthetic report must be reviewed tomorrow.'})
  expect(page.get_by_role('status').filter(has_text='Documento pronto e selecionado')).to_be_visible(timeout=150000)
  page.get_by_role('tab',name='Início',exact=True).click();expect(page.locator('.context-meter')).to_contain_text('1 fonte')
  # The same control is available in all composer placements.
  if context_button.get_attribute('aria-expanded')=='true':context_button.click()
  context_button.click();expect(page.locator('.context-heading')).to_contain_text('1 documento');context_button.click()
  expect(page.locator('.context-meter')).to_contain_text('1 fonte');checks['toggle_preserves_selected_documents']=True
  page.set_viewport_size({'width':390,'height':844});page.screenshot(path='/artifacts/unified-mobile.png',mask=[page.locator('.history-items'),page.locator('.work-user')])
  checks['mobile_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
  context_button.click();expect(page.get_by_role('region',name='Contexto de trabalho')).to_be_visible();checks['mobile_context_works']=True;context_button.click()
  page.set_viewport_size({'width':1600,'height':1100})
  page.evaluate("document.documentElement.dataset.theme='dark'");page.screenshot(path='/artifacts/unified-dark.png',mask=[page.locator('.history-items'),page.locator('.work-user')],mask_color='#0b142b');page.evaluate("document.documentElement.dataset.theme='light'")
  page.get_by_role('tab',name='Histórico',exact=True).click();panel=page.locator('.previous-history-panel')
  panel.get_by_role('button',name='Consultar minhas conversas anteriores',exact=True).click()
  page.get_by_label('Buscar conversas',exact=True).fill(fixture['old_title'])
  card=panel.get_by_role('button').filter(has_text=fixture['old_title']);expect(card).to_have_count(1,timeout=45000);card.click()
  expect(panel.locator('.previous-messages')).to_contain_text('Resposta histórica selecionada')
  expect(panel.locator('.previous-messages')).not_to_contain_text('VERSÃO NÃO SELECIONADA');checks['prior_history_uses_selected_branch']=True
  expect(page.locator('#chat-draft')).to_have_count(0);checks['prior_history_is_read_only_until_explicit_copy']=True
  panel.get_by_role('button',name='Continuar em uma cópia',exact=True).click()
  expect(page.locator('.work-conversation')).to_contain_text('Resposta histórica selecionada',timeout=45000)
  expect(page.locator('.context-meter')).to_contain_text('Sem documentos');checks['prior_attachments_do_not_bypass_current_permissions']=True
  page.get_by_label('Sua mensagem',exact=True).fill('quais suas habilidades?');page.get_by_role('button',name='Enviar solicitação',exact=True).click()
  expect(page.locator('.message:not(.user-message) .markdown').last).to_contain_text('Moara',timeout=90000);expect(page.locator('.moara-processing')).not_to_be_visible(timeout=45000)
  checks['old_conversation_continues_in_current_chat']=True
  context_button.click();expect(page.get_by_role('region',name='Contexto de trabalho')).to_be_visible();context_button.click();checks['context_toggle_available_during_conversation']=True
  page.goto('https://moara.am.trf1.gov.br/moara/desenvolvimento/api');expect(page.get_by_role('heading',name='API para VS Code',exact=True)).to_be_visible();checks['api_key_page_preserved']=True
  page.goto('https://moara.am.trf1.gov.br/moara/chat');expect(page.get_by_label('Sua mensagem',exact=True)).to_be_visible()
  page.get_by_label('Sua mensagem',exact=True).fill('qual a lei que trata de crime de trânsitos?');page.get_by_role('button',name='Enviar solicitação',exact=True).click()
  response=page.locator('.message:not(.user-message) .markdown').last
  expect(response).to_contain_text('Código de Trânsito Brasileiro',timeout=180000);expect(response).to_contain_text(re.compile(r'9\.?503'))
  checks['legal_topic_search_in_chat']=True
  checks['legal_topic_has_official_and_evidence_links']=response.locator('a[href*="senado.leg.br"]').count()>0 and response.locator('a[href*="/legal/evidence/"]').count()>0
  page.get_by_label('Sua mensagem',exact=True).fill('me explique como funciona e os critérios para usar a modalidade diálogo competitivo.');page.get_by_role('button',name='Enviar solicitação',exact=True).click()
  recovered=page.locator('.message:not(.user-message) .markdown').last
  expect(recovered).to_contain_text('inovação',timeout=180000);expect(recovered).to_contain_text(re.compile(r'14\.?133'))
  checks['legal_recovery_question_in_chat']=True

  page.screenshot(path='/artifacts/legal-discovery-chat.png',mask=[page.locator('.history-items'),page.locator('.work-user')],mask_color='#0b142b')
  page.get_by_label('Sua mensagem',exact=True).fill('qual o tema do stf que trata de pessoas que tem HIV tem direito a aposentadoria?');page.get_by_role('button',name='Enviar solicitação',exact=True).click()
  precedent=page.locator('.message:not(.user-message) .markdown').last
  expect(precedent).to_contain_text(re.compile(r'Tema 1\.?310'),timeout=180000);expect(precedent).to_contain_text('reforma militar');expect(precedent).to_contain_text('INSS')
  checks['stf_topic_by_subject_in_chat']=True
  checks['stf_official_links_present']=precedent.locator('a[href*="portal.stf.jus.br"]').count()>=2
  page.locator('.message:not(.user-message) .markdown').last.scroll_into_view_if_needed()
  page.screenshot(path='/artifacts/jurisprudence-chat.png',mask=[page.locator('.history-items'),page.locator('.work-user')],mask_color='#0b142b')


  citation=precedent.locator('a.moara-source').first;expected_source=citation.get_attribute('href')
  citation.hover();hint=page.get_by_role('dialog',name='Fonte externa');expect(hint).to_be_visible()
  expect(hint.get_by_role('link',name=re.compile('Abrir fonte oficial'))).to_have_attribute('href',expected_source)
  checks['source_hint_matches_inline_citation']=True
  hint.hover();expect(hint).to_be_visible();checks['source_hint_remains_clickable_on_hover']=True
  expect(hint.get_by_role('link')).to_have_attribute('target','_blank');expect(hint.get_by_role('link')).to_have_attribute('rel',re.compile('noopener'))
  checks['source_opens_external_official_link_safely']=urlsplit(expected_source).hostname in {'portal.stf.jus.br','www2.camara.leg.br'}
  page.screenshot(path='/artifacts/citations-desktop.png',mask=[page.locator('.history-items'),page.locator('.work-user')],mask_color='#0b142b')
  page.keyboard.press('Escape');expect(hint).to_have_count(0)
  citation.evaluate("e=>e.blur()");citation.focus();expect(hint).to_be_visible();page.keyboard.press('Escape');expect(hint).to_have_count(0)
  checks['source_hint_keyboard_and_escape']=True
  page.set_viewport_size({'width':390,'height':844});citation.scroll_into_view_if_needed();citation.tap();expect(hint).to_be_visible()
  bounds=hint.bounding_box();checks['source_hint_mobile_inside_viewport']=bounds['x']>=0 and bounds['x']+bounds['width']<=391 and bounds['y']>=0 and bounds['y']+bounds['height']<=845
  page.screenshot(path='/artifacts/citations-mobile.png',mask=[page.locator('.history-items'),page.locator('.work-user')],mask_color='#0b142b')
  hint.get_by_role('button',name='Fechar fonte').tap();expect(hint).to_have_count(0);checks['source_hint_touch_can_close']=True
  page.set_viewport_size({'width':1600,'height':1100})

  # Real, synthetic native account: authorization is tested against HTTP APIs, not just menus.
  def api_call(target,path,method='GET',body=None):
   return target.evaluate("""async({path,method,body})=>{let csrf='';if(method!=='GET'){const me=await(await fetch('/moara/api/v1/auth/me')).json();csrf=me.csrf_token||'';}const r=await fetch('/moara/api/v1'+path,{method,headers:{'Content-Type':'application/json','X-Moara-CSRF':csrf},...(body===null?{}:{body:JSON.stringify(body)})});return {status:r.status,data:await r.json()};}""",{'path':path,'method':method,'body':body})
  import secrets,time
  title='Fontes QA '+str(time.time_ns())
  fixture_chat=api_call(page,'/chats','POST',{'title':title});assert fixture_chat['status']==201
  fixture_chat=fixture_chat['data'];chats.append(fixture_chat['id']);checkpoint(context)
  source_url='https://www2.camara.leg.br/legin/fed/lei/1990/lei-8112-11-dezembro-1990-322161-normaatualizada-pl.html'
  source_text='Trecho sintetico de teste [L1.1].\n\n[L1.1] art8 - [fonte oficial]('+source_url+').\n\n`[L1.1]`\n\n[Imitacao](https://portal.stf.jus.br.example.invalid/)\n\n<a class="moara-source" href="https://portal.stf.jus.br.example.invalid/">Forged</a><span class="source-hint">Forged panel</span><script>window.moaraSourceInjected=true</script>\n\n[Invalido](javascript:alert(1))'
  saved=api_call(page,'/chats/'+fixture_chat['id'],'PUT',{'title':title,'profile_id':'auto','assistant_id':'auto','document_ids':[],'expected_updated_at':fixture_chat['updated_at'],'messages':[{'role':'assistant','content':source_text}]});assert saved['status']==200
  page.goto('https://moara.am.trf1.gov.br/moara/chat');page.locator('.history-item').filter(has_text=title).click()
  fixture_message=page.locator('.message .markdown').last
  expect(fixture_message.locator('p').first.locator('a.moara-source')).to_have_attribute('href',source_url)
  checks['historical_citation_resolves_from_same_message']=True
  checks['code_citations_not_rewritten']=fixture_message.locator('code a').count()==0
  checks['lookalike_domain_not_labeled_official']=fixture_message.locator('a.moara-source[href*="example.invalid"]').count()==0
  checks['message_cannot_forge_source_controls']=fixture_message.locator('.source-hint,.source-hint-heading,a.moara-source[href*="example.invalid"]').count()==0
  checks['source_content_remains_sanitized']=not page.evaluate('Boolean(window.moaraSourceInjected)') and fixture_message.locator('script,a[href^="javascript:"]').count()==0
  email='rbac-qa-'+str(time.time_ns())+'@example.invalid';label='RBAC QA '+str(time.time_ns())
  result=api_call(page,'/admin/accounts','POST',{'name':label,'email':email,'roles':['user']})
  assert result['status']==201
  account=result['data']['id'];rbac_accounts.append(account);checkpoint(context);temporary=result['data']['temporary_password'];final_password=secrets.token_urlsafe(30)
  user_context=browser.new_context(viewport={'width':1400,'height':1000});configure(user_context);user=user_context.new_page()
  def user_login(password):
   user.goto('https://moara.am.trf1.gov.br/moara/login');expect(user.locator('select[name=organization]')).to_be_enabled(timeout=30000)
   user.locator('select[name=organization]').select_option('local');user.locator('input[name=email]').fill(email);user.locator('input[name=password]').fill(password)
   user.get_by_role('button',name=re.compile('^Entrar')).click()
  try:
   user_login(temporary);expect(user.get_by_role('heading',name='Defina sua senha')).to_be_visible(timeout=30000)
   user.locator('input[name=password]').fill(final_password);user.locator('input[name=confirm]').fill(final_password);user.get_by_role('button',name='Salvar senha').click()
   expect(user.get_by_role('heading',name='Como posso ajudar você hoje?')).to_be_visible(timeout=30000)
   me=api_call(user,'/auth/me')['data'];checks['new_user_chat_only']=set(me['permissions'])=={'chat.use','history.read','history.manage','profiles.read','identity.read'}
   checks['rbac_blocks_direct_api_access']=all(api_call(user,path)['status']==403 for path in ['/admin/accounts','/admin/roles','/models','/connectors/sources','/platform/resources','/developer/configuration','/status'])
   checks['user_cannot_grant_own_admin']=api_call(user,'/admin/accounts/'+account,'PUT',{'active':True,'roles':['administrator']})['status']==403
   checks['personal_history_owner_isolation']=api_call(user,'/chats/'+chats[-1])['status']==404
   checks['restricted_menus_hidden']=user.locator('a[href="/moara/acessos"],a[href="/moara/desenvolvimento/api"],a[href="/moara/fontes"]').count()==0 and user.get_by_role('tab',name='Documentos',exact=True).count()==0
   user.get_by_label('Sua mensagem',exact=True).fill('Oi');user.get_by_role('button',name='Enviar solicitação',exact=True).click()
   expect(user.locator('.message:not(.user-message) .markdown').last).to_contain_text('Moara',timeout=60000);checks['restricted_user_chat_works']=True
   user.get_by_label('Sua mensagem',exact=True).fill('qual o tema do stf que trata de pessoas que tem HIV tem direito a aposentadoria?');user.get_by_role('button',name='Enviar solicitação',exact=True).click()
   try:
    expect(user.locator('.message:not(.user-message) .markdown').last).to_contain_text(re.compile(r'Tema 1\.?310'),timeout=180000)
   except Exception:
    Path('/artifacts/restricted-stf-diagnostic.json').write_text(json.dumps({'alerts':user.locator('[role=alert]').all_text_contents(),'messages':user.locator('.message').all_text_contents(),'draft':user.get_by_label('Sua mensagem',exact=True).input_value()},ensure_ascii=True))
    raise
   checks['chat_only_user_can_research_stf_subject']=True

   user.screenshot(path='/artifacts/rbac-user.png',mask=[user.locator('.work-user')])
   page.goto('https://moara.am.trf1.gov.br/moara/acessos');expect(page.get_by_role('heading',name='Identidade e acessos')).to_be_visible()
   page.get_by_label('Buscar usuário').fill(label)
   page.get_by_role('row').filter(has_text=label).get_by_role('button',name='Permissões',exact=True).click()
   page.locator('input[name=role-developer]').check();page.get_by_role('button',name='Salvar permissões',exact=True).click()
   expect(page.get_by_role('status')).to_contain_text('Permissões atualizadas')
   checks['grant_revokes_existing_session']=api_call(user,'/auth/me')['status']==401
   user_login(final_password);expect(user.get_by_role('heading',name='Como posso ajudar você hoje?')).to_be_visible(timeout=30000)
   checks['granted_module_effective']=api_call(user,'/developer/configuration')['status']==200
   user.goto('https://moara.am.trf1.gov.br/moara/desenvolvimento/api');expect(user.get_by_role('heading',name='API para VS Code',exact=True)).to_be_visible()
   checks['granted_module_ui_works']=True
   page.get_by_role('row').filter(has_text=label).get_by_role('button',name='Permissões',exact=True).click()
   page.locator('input[name=role-developer]').uncheck();page.get_by_role('button',name='Salvar permissões',exact=True).click()
   expect(page.get_by_role('heading',name='Permissões de '+label)).to_have_count(0)
   checks['revoke_invalidates_existing_session']=api_call(user,'/auth/me')['status']==401
   user_login(final_password);expect(user.get_by_role('heading',name='Como posso ajudar você hoje?')).to_be_visible(timeout=30000)
   checks['revoked_module_denied']=api_call(user,'/developer/configuration')['status']==403
   page.screenshot(path='/artifacts/rbac-admin.png',mask=[page.locator('.table-wrap'),page.locator('.profile')])
   page.set_viewport_size({'width':390,'height':844});checks['rbac_admin_mobile_no_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1');page.set_viewport_size({'width':1600,'height':1100})
  finally:
   current_user=api_call(user,'/auth/me')
   if current_user['status']==200:
    for chat in api_call(user,'/chats')['data']:
     assert api_call(user,'/chats/'+chat['id']+'/archive','POST')['status']==200
   disabled=api_call(page,'/admin/accounts/'+account,'PUT',{'active':False,'roles':['user']})
   checks['synthetic_rbac_account_disabled']=disabled['status']==200
   user_context.close()

  checks['no_javascript_errors']=not errors
 finally:
  try:
   checks['synthetic_resources_archived']=page.evaluate("""async({chats,resources})=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();let ok=true;for(const id of chats){const r=await fetch('/moara/api/v1/chats/'+id+'/archive',{method:'POST',headers:{'X-Moara-CSRF':me.csrf_token}});ok=ok&&r.ok;}for(const id of resources){const row=await(await fetch('/moara/api/v1/platform/resources/'+id)).json();const r=await fetch('/moara/api/v1/platform/resources/'+id+'/archive',{method:'POST',headers:{'Content-Type':'application/json','X-Moara-CSRF':me.csrf_token},body:JSON.stringify({version:row.version})});ok=ok&&r.ok;}return ok;}""",{'chats':chats,'resources':resources})
  finally:checkpoint(context);context.close();browser.close()
print(json.dumps({'checks':checks,'passed':True}));assert checks and all(checks.values())
