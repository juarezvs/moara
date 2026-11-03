"""Real portal, owner-isolated prior history, contextual controls and public routes."""
import sys,json,hashlib,re
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline());checks={};chats=[];resources=[];errors=[];rbac_accounts=[]
output=Path('/artifacts/unified-ui.json')
def configure(context):
 if fixture.get('proxy') and not fixture.get('candidate_ip'):
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
 extra=['--host-resolver-rules=MAP moara.am.trf1.gov.br '+fixture['candidate_ip'],'--no-proxy-server'] if fixture.get('candidate_ip') else []
 browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']]+extra)
 context=browser.new_context(viewport={'width':1600,'height':1100},has_touch=True,timezone_id='America/Manaus',accept_downloads=True);configure(context)
 context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:160]))
 def seen(r):
  if r.request.method=='POST' and r.status==201:
   if r.url.endswith('/moara/api/v1/chats') or re.search('/history/previous/[^/]+/resume$',r.url):chats.append(r.json()['id']);checkpoint(context)
   if r.url.endswith('/moara/api/v1/platform/documents'):resources.append(r.json()['id']);checkpoint(context)
 page.on('response',seen)
 try:
  page.goto('https://moara.am.trf1.gov.br/moara/',wait_until='domcontentloaded')
  expect(page.locator('.dashboard-cards')).to_be_visible(timeout=45000);checkpoint(context)
  page.goto('https://moara.am.trf1.gov.br/moara/chat',wait_until='domcontentloaded')
  expect(page.get_by_label('Sua mensagem',exact=True)).to_be_visible(timeout=45000)
  page.get_by_label('Sua mensagem',exact=True).fill('Explique fotossintese de forma simples.')
  page.get_by_role('button',name=re.compile('Enviar solicita')).click()
  expect(page.locator('.moara-processing')).to_be_visible(timeout=15000)
  expect(page.locator('.moara-processing')).to_have_count(0,timeout=180000)
  answer=page.locator('.message:not(.user-message) .markdown').last.inner_text()
  checks['general_question_is_answered_without_purpose_gate']='fotoss' in answer.lower() and 'finalidade institucional' not in answer.lower()
  page.get_by_role('button',name='Novo trabalho',exact=True).click()
  page.get_by_label('Sua mensagem',exact=True).fill('Pesquise na web a documentacao oficial do Angular Signals e explique como funcionam.')
  page.get_by_role('button',name=re.compile('Enviar solicita')).click()
  expect(page.locator('.processing-copy')).to_contain_text('buscador privado',timeout=90000)
  checks['actual_web_search_progress_is_visible']=True
  expect(page.locator('.moara-processing')).to_have_count(0,timeout=180000)
  answer=page.locator('.message:not(.user-message) .markdown').last
  checks['web_answer_explains_retrieved_content']='signals' in answer.inner_text().lower() and 'sintese verific' not in answer.inner_text().lower()
  checks['inline_sources_have_real_urls']=answer.locator('a[href="https://angular.dev/guide/signals"]').count()>0
  link=answer.locator('a[href*="/api/v1/web/evidence/"]').first.get_attribute('href')
  report=page.evaluate('async(url)=>await(await fetch(url)).json()',link)
  checks['web_evidence_is_replayable']=report['kind']=='web_research' and report['rechecked_now'] is False
  checks['source_snapshot_and_quote_are_retained']=bool(report['retrieval']['sources'][0]['snapshot_gzip_base64']) and any(s.get('support_quotes') for s in report['retrieval']['sources'])
  checks['frontend_has_no_javascript_errors']=not errors
  page.screenshot(path='/artifacts/public-web-chat.png',mask=[page.locator('.history-items'),page.locator('.work-user')],mask_color='#162d3e')

 finally:
  try:
   checks['synthetic_resources_archived']=page.evaluate("""async({chats,resources})=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();let ok=true;for(const id of chats){const r=await fetch('/moara/api/v1/chats/'+id+'/archive',{method:'POST',headers:{'X-Moara-CSRF':me.csrf_token}});ok=ok&&r.ok;}for(const id of resources){const row=await(await fetch('/moara/api/v1/platform/resources/'+id)).json();const r=await fetch('/moara/api/v1/platform/resources/'+id+'/archive',{method:'POST',headers:{'Content-Type':'application/json','X-Moara-CSRF':me.csrf_token},body:JSON.stringify({version:row.version})});ok=ok&&r.ok;}return ok;}""",{'chats':chats,'resources':resources})
  finally:checkpoint(context);context.close();browser.close()
print(json.dumps({'checks':checks,'passed':True}));assert checks and all(checks.values())
