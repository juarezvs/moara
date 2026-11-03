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
  page.goto('https://moara.am.trf1.gov.br/moara/chat',wait_until='domcontentloaded');expect(page.get_by_label('Sua mensagem',exact=True)).to_be_visible(timeout=45000);checkpoint(context)
  context.grant_permissions(['clipboard-read','clipboard-write'],origin='https://moara.am.trf1.gov.br')
  page.get_by_label('Sua mensagem',exact=True).fill('qual tema do stf que trata de remedio de alto custo e suas respectivas teses')
  page.get_by_role('button',name=re.compile('Enviar solicita')).click();expect(page.locator('.moara-processing')).to_be_visible(timeout=30000);checks['real_progress_visible']=True
  expect(page.locator('.moara-processing')).to_have_count(0,timeout=180000)
  response=page.locator('.work-conversation .message:not(.user-message)').last;expect(response).to_contain_text('Tema 6',timeout=30000);expect(response).to_contain_text('1.234');expect(response.locator('h2').first).to_be_visible();checks['real_question_has_both_themes_and_headings']=True
  expect(response.locator('table')).to_have_count(1);checks['comparison_table_rendered']=True
  checks['list_markers_visible']=response.locator('li').first.evaluate('(e)=>getComputedStyle(e).display==="list-item"&&getComputedStyle(e).listStyleType!=="none"')
  expect(response.locator('details')).to_have_count(1);response.locator('details summary').click();checks['full_thesis_expands']=response.locator('details').evaluate('(e)=>e.open');response.locator('details summary').click()
  user=page.locator('.work-conversation .user-message').last
  a=user.bounding_box();b=response.bounding_box();checks['question_and_answer_share_reading_width']=abs(a['width']-b['width'])<=2 and abs(a['x']-b['x'])<=2
  source=response.locator('a.moara-source').first;source.scroll_into_view_if_needed();source.hover();expect(page.locator('.source-hint')).to_be_visible();checks['official_source_hint_and_link_work']=page.locator('.source-hint>a').get_attribute('href').startswith('https://portal.stf.jus.br/');page.keyboard.press('Escape')
  response.get_by_role('button',name='Copiar resposta da Moara').click();expect(response.get_by_role('button',name='Copiar resposta da Moara')).to_contain_text('Copiado');copied=page.evaluate('navigator.clipboard.readText()');checks['copy_response_includes_source_links']='Tema 6' in copied and 'https://portal.stf.jus.br/' in copied
  page.locator('.work-conversation .messages').evaluate('(e)=>e.scrollTop=0');page.screenshot(path='/artifacts/chat-reading-desktop.png',mask=[page.locator('.history-items'),page.locator('.work-user')],mask_color='#0b142b')
  page.set_viewport_size({'width':390,'height':844});page.locator('.work-conversation .messages').evaluate('(e)=>e.scrollTop=0');checks['mobile_has_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1');a=user.bounding_box();b=response.bounding_box();checks['mobile_question_answer_widths_match']=abs(a['width']-b['width'])<=2
  page.screenshot(path='/artifacts/chat-reading-mobile.png',mask=[page.locator('.history-items'),page.locator('.work-user')],mask_color='#0b142b');checks['no_javascript_errors']=not errors

 finally:
  try:
   checks['synthetic_resources_archived']=page.evaluate("""async({chats,resources})=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();let ok=true;for(const id of chats){const r=await fetch('/moara/api/v1/chats/'+id+'/archive',{method:'POST',headers:{'X-Moara-CSRF':me.csrf_token}});ok=ok&&r.ok;}for(const id of resources){const row=await(await fetch('/moara/api/v1/platform/resources/'+id)).json();const r=await fetch('/moara/api/v1/platform/resources/'+id+'/archive',{method:'POST',headers:{'Content-Type':'application/json','X-Moara-CSRF':me.csrf_token},body:JSON.stringify({version:row.version})});ok=ok&&r.ok;}return ok;}""",{'chats':chats,'resources':resources})
  finally:checkpoint(context);context.close();browser.close()
print(json.dumps({'checks':checks,'passed':True}));assert checks and all(checks.values())
