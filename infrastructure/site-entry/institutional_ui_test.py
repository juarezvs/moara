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
 context=browser.new_context(viewport={'width':1600,'height':1100},has_touch=True,timezone_id='America/Manaus',accept_downloads=True);configure(context)
 context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:160]))
 def seen(r):
  if r.request.method=='POST' and r.status==201:
   if r.url.endswith('/moara/api/v1/chats') or re.search('/history/previous/[^/]+/resume$',r.url):chats.append(r.json()['id']);checkpoint(context)
   if r.url.endswith('/moara/api/v1/platform/documents'):resources.append(r.json()['id']);checkpoint(context)
 page.on('response',seen)
 try:
  page.goto('https://moara.am.trf1.gov.br/',wait_until='domcontentloaded')
  # A redirected Playwright route can continue on the public origin; a second
  # explicit navigation keeps the private candidate under interception.
  if fixture.get('proxy'):page.goto('https://moara.am.trf1.gov.br/moara/chat',wait_until='domcontentloaded')
  expect(page.get_by_label('Sua mensagem',exact=True)).to_be_visible(timeout=45000);checkpoint(context)
  Path('/artifacts/home-diagnostic.json').write_text(json.dumps({'url':page.url,'h1':page.locator('h1').all_text_contents(),'scripts':page.locator('script[src]').evaluate_all('(es)=>es.map(e=>e.src)'),'messages':page.locator('.message').count(),'overview':page.locator('.workspace-overview').count()}))
  page.screenshot(path='/artifacts/home-diagnostic.png',mask=[page.locator('.history-items'),page.locator('.work-user')],mask_color='#142b3f')
  if page.get_by_role('button',name='Ativar tema claro').is_visible():
   page.get_by_role('button',name='Ativar tema claro').click();expect(page.locator('html')).to_have_attribute('data-theme','light')
  expect(page.locator('.workspace-overview h1')).to_contain_text('Seu trabalho');checks['root_opens_redesigned_workspace']='/moara/chat' in page.url
  checks['single_sidebar_work_navigation']=page.locator('.work-history .work-nav [role=tablist]').count()==1 and page.locator('.work-main>.work-nav').count()==0
  checks['space_background_removed']=page.locator('.legal-workbench').evaluate('(e)=>getComputedStyle(e).backgroundImage')=='none'
  checks['header_brand_preserved']=page.locator('.header-brand img[src="brand/mark.svg"]').count()==1 and page.locator('.intro-mark').count()==0
  expect(page.locator('.welcome-aside')).to_be_visible();checks['editorial_welcome_and_guidance_visible']=True
  page.get_by_role('button',name='Contexto',exact=True).click();expect(page.locator('#work-context')).to_be_visible();page.get_by_role('button',name='Contexto',exact=True).click();expect(page.locator('#work-context')).to_have_count(0);checks['context_toggle_preserved']=True
  page.get_by_role('button',name='Opções',exact=True).click();expect(page.locator('#work-settings')).to_be_visible();page.get_by_role('button',name='Opções',exact=True).click();checks['assistant_and_model_options_preserved']=True
  page.get_by_role('button',name='Planejar',exact=True).click();expect(page.locator('.composer-header')).to_contain_text('PLANO DE TRABALHO');page.get_by_role('button',name='Minuta',exact=True).click();expect(page.locator('.composer-header')).to_contain_text('RASCUNHO DE DOCUMENTO');page.get_by_role('button',name='Conversar',exact=True).click();checks['work_modes_preserved']=True
  page.locator('.work-administration summary').click();expect(page.locator('.work-central a[href="/moara/acessos"]')).to_be_visible();page.locator('.work-administration summary').click();checks['administration_links_preserved']=True
  for area in ['historico','documentos','modelos','referencias','acervo','inicio']:
   page.locator('#work-tab-'+area).click();expect(page.locator('#work-tab-'+area)).to_have_attribute('aria-selected','true')
  checks['all_work_areas_operate']=True
  page.locator('#work-tab-inicio').focus();page.keyboard.press('ArrowDown');expect(page.locator('#work-tab-historico')).to_be_focused();page.keyboard.press('Home');expect(page.locator('#work-tab-inicio')).to_be_focused();checks['keyboard_navigation_preserved']=True;page.locator('.workspace-overview h1').click()
  checks['desktop_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
  top=page.locator('.work-space-label').bounding_box();header=page.locator('.moara-site-header').bounding_box();checks['sidebar_top_not_clipped_by_header']=top['y']>=header['y']+header['height']-1
  masks=[page.locator('.history-items'),page.locator('.work-user')];page.screenshot(path='/artifacts/institutional-home-desktop.png',mask=masks,mask_color='#142b3f')
  page.get_by_role('button',name='Ativar tema escuro').click();expect(page.locator('html')).to_have_attribute('data-theme','dark');checks['dark_mode_operates']=page.locator('html').get_attribute('data-theme')=='dark' or page.locator('body').get_attribute('data-theme')=='dark';page.screenshot(path='/artifacts/institutional-home-dark.png',mask=masks,mask_color='#142b3f');page.get_by_role('button',name='Ativar tema claro').click();expect(page.locator('html')).to_have_attribute('data-theme','light')
  page.set_viewport_size({'width':1024,'height':900});checks['tablet_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
  page.set_viewport_size({'width':390,'height':844});expect(page.get_by_role('button',name=re.compile('Mostrar .reas e hist'))).to_be_visible();checks['mobile_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1');page.screenshot(path='/artifacts/institutional-home-mobile.png')
  page.get_by_role('button',name=re.compile('Mostrar .reas e hist')).click();expect(page.locator('.work-history.mobile-open')).to_be_visible();page.keyboard.press('Tab');checks['mobile_drawer_traps_keyboard_focus']=page.locator('.work-history').evaluate('(e)=>e.contains(document.activeElement)');page.keyboard.press('Escape');expect(page.locator('.work-history.mobile-open')).to_have_count(0);checks['mobile_drawer_escape_and_focus']=page.get_by_role('button',name=re.compile('Mostrar .reas e hist')).evaluate('(e)=>e===document.activeElement')
  page.get_by_role('button',name=re.compile('Mostrar .reas e hist')).click();page.locator('#work-tab-referencias').click();expect(page.locator('.reference-switch')).to_be_visible();checks['mobile_navigation_selects_and_closes']=page.locator('.work-history.mobile-open').count()==0
  page.get_by_role('button',name=re.compile('Mostrar .reas e hist')).click();page.locator('#work-tab-inicio').click();page.get_by_label('Sua mensagem',exact=True).fill('Oi');page.get_by_role('button',name=re.compile('Enviar solicita')).click();expect(page.locator('.message:not(.user-message) .markdown')).not_to_be_empty(timeout=90000);checks['real_chat_still_operates']=True
  checks['no_javascript_errors']=not errors

 finally:
  try:
   checks['synthetic_resources_archived']=page.evaluate("""async({chats,resources})=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();let ok=true;for(const id of chats){const r=await fetch('/moara/api/v1/chats/'+id+'/archive',{method:'POST',headers:{'X-Moara-CSRF':me.csrf_token}});ok=ok&&r.ok;}for(const id of resources){const row=await(await fetch('/moara/api/v1/platform/resources/'+id)).json();const r=await fetch('/moara/api/v1/platform/resources/'+id+'/archive',{method:'POST',headers:{'Content-Type':'application/json','X-Moara-CSRF':me.csrf_token},body:JSON.stringify({version:row.version})});ok=ok&&r.ok;}return ok;}""",{'chats':chats,'resources':resources})
  finally:checkpoint(context);context.close();browser.close()
print(json.dumps({'checks':checks,'passed':True}));assert checks and all(checks.values())
