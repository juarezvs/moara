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
  page.goto('https://moara.am.trf1.gov.br/moara/chat?area=referencias&catalogo=stf',wait_until='domcontentloaded')
  expect(page.get_by_role('heading',name='Acervo de teses do STF')).to_be_visible(timeout=45000);checkpoint(context)
  expect(page.locator('.stf-card')).to_have_count(20,timeout=30000)
  metadata=page.evaluate("async()=>await(await fetch('/moara/api/v1/legal/stf-theses?limit=1')).json()")
  expect(page.locator('.stf-summary')).to_contain_text(str(metadata['counts']['com']));expect(page.locator('.stf-summary')).to_contain_text(str(metadata['counts']['sem']))
  checks['complete_bank_counts_visible']=True
  original=page.locator('.stf-card h3').first.inner_text();page.locator('.stf-pages').get_by_role('button',name=re.compile('Pr')).click()
  expect(page.locator('.stf-pages')).to_contain_text(re.compile('P.gina 2'));checks['pagination_changes_records']=page.locator('.stf-card h3').first.inner_text()!=original
  page.get_by_label('Banco',exact=True).select_option('sem');expect(page.locator('.stf-card .stf-badge.no-rg')).to_have_count(20)
  checks['without_repercussion_filter_preserved']=page.locator('.stf-card .stf-badge:not(.no-rg)').count()==0
  page.get_by_label(re.compile('Buscar por palavras')).fill('ICMS PIS COFINS');page.get_by_role('button',name='Pesquisar teses').click()
  expect(page.get_by_role('heading',name='Tema 1394',exact=True)).to_be_visible(timeout=30000)
  checks['text_search_in_without_rg_bank']=True
  page.get_by_label('Banco',exact=True).select_option('com');expect(page.get_by_role('heading',name='Tema 69',exact=True)).to_be_visible(timeout=30000)
  page.get_by_label(re.compile('Buscar por palavras')).fill('69');page.get_by_role('button',name='Pesquisar teses').click();expect(page.locator('.stf-card')).to_have_count(1)
  expect(page.locator('.stf-card')).to_contain_text('RE 574706');checks['exact_theme_search_and_leading_case']=True
  checks['official_source_links']=page.locator('.stf-card a[href="https://portal.stf.jus.br/jurisprudenciaRepercussao/tema.asp?num=69"]').count()==1
  checks['snapshot_limit_notice_visible']='pendente' in page.locator('.stf-notice').inner_text() and 'modula' in page.locator('.stf-notice').inner_text()
  page.screenshot(path='/artifacts/stf-catalog-desktop.png',mask=[page.locator('.history-items'),page.locator('.work-user')],mask_color='#0b142b')
  page.on('response',lambda response: Path('/artifacts/stf-download-diagnostic.json').write_text(json.dumps({'status':response.status,'headers':{k:v for k,v in response.headers.items() if k in ['content-disposition','content-type','content-length','content-encoding']}})) if '/stf-theses/export' in response.url else None)
  with page.expect_download() as download_info:page.get_by_role('button',name='Baixar acervo e fontes').click()
  try:download_info.value.save_as('/artifacts/stf-catalog-export.json')
  except Exception:raise RuntimeError('Catalogue browser download failure: '+str(download_info.value.failure())) from None
  exported=json.loads(Path('/artifacts/stf-catalog-export.json').read_text())
  checks['complete_export_downloads_in_browser']=len(exported['items'])==sum(metadata['counts'].values())
  page.set_viewport_size({'width':390,'height':844});checks['mobile_has_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
  page.screenshot(path='/artifacts/stf-catalog-mobile.png',mask=[page.locator('.history-items'),page.locator('.work-user')],mask_color='#0b142b')
  page.get_by_role('button',name=re.compile('Preparar confer')).click();expect(page.get_by_label('Sua mensagem',exact=True)).to_have_value(re.compile('Tema 69'))
  checks['selected_theme_prepares_live_check_in_chat']=True;checks['no_javascript_errors']=not errors
 finally:
  try:
   checks['synthetic_resources_archived']=page.evaluate("""async({chats,resources})=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();let ok=true;for(const id of chats){const r=await fetch('/moara/api/v1/chats/'+id+'/archive',{method:'POST',headers:{'X-Moara-CSRF':me.csrf_token}});ok=ok&&r.ok;}for(const id of resources){const row=await(await fetch('/moara/api/v1/platform/resources/'+id)).json();const r=await fetch('/moara/api/v1/platform/resources/'+id+'/archive',{method:'POST',headers:{'Content-Type':'application/json','X-Moara-CSRF':me.csrf_token},body:JSON.stringify({version:row.version})});ok=ok&&r.ok;}return ok;}""",{'chats':chats,'resources':resources})
  finally:checkpoint(context);context.close();browser.close()
print(json.dumps({'checks':checks,'passed':True}));assert checks and all(checks.values())
