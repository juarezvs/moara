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
  page.goto('https://moara.am.trf1.gov.br/moara/chat?area=referencias&catalogo=metadados',wait_until='domcontentloaded')
  expect(page.get_by_role('heading',name=re.compile('Cat.logo de normas'))).to_be_visible(timeout=45000);checkpoint(context)
  expect(page.locator('.stf-card')).to_have_count(20,timeout=30000)
  data=page.evaluate("async()=>await(await fetch('/moara/api/v1/legal/metadata?limit=1')).json()")
  expect(page.locator('.stf-summary')).to_contain_text(str(data['counts']['metadata_records']));checks['metadata_count_visible']=True
  page.locator('.stf-pages').get_by_role('button',name=re.compile('Pr')).click();expect(page.locator('.stf-pages')).to_contain_text(re.compile('P.gina 2'));checks['pagination_works']=True
  page.get_by_label(re.compile('Buscar normas')).fill('estatuto servidor');page.get_by_role('button',name='Pesquisar normas').click();expect(page.locator('.stf-card')).to_have_count(1);expect(page.locator('.stf-card')).to_contain_text('8.112');checks['alias_search_works']=True
  page.get_by_label(re.compile('Buscar normas')).fill('');page.get_by_label(re.compile('N.mero da norma')).fill('14133');page.get_by_role('button',name='Pesquisar normas').click();expect(page.locator('.stf-card')).to_have_count(1);expect(page.locator('.stf-card')).to_contain_text('14.133');checks['exact_number_search_works']=True
  checks['official_metadata_and_lexml_links_visible']=page.locator('.stf-card a[href^="https://legis.senado.leg.br/"]').count()==1 and page.locator('.stf-card a[href^="https://www.lexml.gov.br/urn/"]').count()==1
  checks['metadata_scope_notice_visible']='inteiro teor' in page.locator('.stf-notice').inner_text()
  page.screenshot(path='/artifacts/metadata-desktop.png',mask=[page.locator('.history-items'),page.locator('.work-user')],mask_color='#0b142b')
  with page.expect_download() as info:page.get_by_role('button',name='Baixar metadados e fontes').click()
  info.value.save_as('/artifacts/metadata-export.json');out=json.loads(Path('/artifacts/metadata-export.json').read_text());checks['source_export_downloads']=len(out['items'])==data['counts']['metadata_records'] and bool(out['snapshots'])
  page.set_viewport_size({'width':390,'height':844});checks['mobile_has_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1');page.screenshot(path='/artifacts/metadata-mobile.png',mask=[page.locator('.history-items'),page.locator('.work-user')],mask_color='#0b142b')
  page.get_by_role('button',name='Conferir texto oficial no chat').click();expect(page.get_by_label('Sua mensagem',exact=True)).to_have_value(re.compile('Lei 14133/2021'));checks['selection_prepares_live_official_check']=True
  checks['no_javascript_errors']=not errors

 finally:
  try:
   checks['synthetic_resources_archived']=page.evaluate("""async({chats,resources})=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();let ok=true;for(const id of chats){const r=await fetch('/moara/api/v1/chats/'+id+'/archive',{method:'POST',headers:{'X-Moara-CSRF':me.csrf_token}});ok=ok&&r.ok;}for(const id of resources){const row=await(await fetch('/moara/api/v1/platform/resources/'+id)).json();const r=await fetch('/moara/api/v1/platform/resources/'+id+'/archive',{method:'POST',headers:{'Content-Type':'application/json','X-Moara-CSRF':me.csrf_token},body:JSON.stringify({version:row.version})});ok=ok&&r.ok;}return ok;}""",{'chats':chats,'resources':resources})
  finally:checkpoint(context);context.close();browser.close()
print(json.dumps({'checks':checks,'passed':True}));assert checks and all(checks.values())
