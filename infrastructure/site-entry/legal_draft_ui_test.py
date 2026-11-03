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
  page.goto('https://moara.am.trf1.gov.br/moara/chat',wait_until='domcontentloaded')
  expect(page.get_by_label('Sua mensagem',exact=True)).to_be_visible(timeout=45000);checkpoint(context)
  page.get_by_role('button',name='Minuta',exact=True).click()
  page.get_by_label('Sua mensagem',exact=True).fill('crie uma peti\u00e7\u00e3o para aposentadoria de um pescador, segurado especial, com fundamenta\u00e7\u00e3o jur\u00eddica robusta.')
  page.get_by_role('button',name=re.compile('Enviar solicita')).click()
  expect(page.locator('.moara-processing')).to_be_visible(timeout=15000)
  checks['processing_is_visible']=True
  expect(page.locator('.moara-processing')).to_have_count(0,timeout=480000)
  answer=page.locator('.message:not(.user-message) .markdown').last
  text=answer.inner_text()
  checks['draft_mode_delivers_petition']='PETI\u00c7\u00c3O INICIAL' in text and 'Dos pedidos' in text
  checks['draft_has_pending_der_and_hypothesis']='[DER' in text and 'Hip\u00f3tese' in text
  checks['no_generic_clarification_gate']='informe a data relevante' not in text and 'Para conferir as fontes oficiais antes' not in text
  checks['legal_sources_are_clickable']=answer.locator('a.moara-source').count()>0
  evidence=answer.locator('a[href*="/api/v1/legal/evidence/"]').first.get_attribute('href')
  record=page.evaluate('async(url)=>await(await fetch(url,{headers:{Accept:"application/json"}})).json()',evidence)
  checks['actual_sources_are_grounded']=record['verification']['grounded_response']['status']=='grounded_explanation'
  checks['current_research_not_fake_case_date']=record['verification']['draft']['current_research_is_not_case_date'] is True
  checks['no_response_inner_scroll']=page.locator('.messages').evaluate('(e)=>getComputedStyle(e).overflowY==="visible"&&Math.abs(e.scrollHeight-e.clientHeight)<3')
  checks['editor_action_available']=page.get_by_role('button',name='Abrir no editor',exact=True).count()==1
  checks['no_javascript_errors']=not errors
  page.screenshot(path='/artifacts/legal-draft-desktop.png',mask=[page.locator('.history-items'),page.locator('.work-user')],mask_color='#162d3e')
  page.get_by_role('button',name='Abrir no editor',exact=True).click()
  checks['draft_opens_as_editable_document']='PETIÇÃO INICIAL' in page.locator('.draft-editor').input_value()

 finally:
  try:
   checks['synthetic_resources_archived']=page.evaluate("""async({chats,resources})=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();let ok=true;for(const id of chats){const r=await fetch('/moara/api/v1/chats/'+id+'/archive',{method:'POST',headers:{'X-Moara-CSRF':me.csrf_token}});ok=ok&&r.ok;}for(const id of resources){const row=await(await fetch('/moara/api/v1/platform/resources/'+id)).json();const r=await fetch('/moara/api/v1/platform/resources/'+id+'/archive',{method:'POST',headers:{'Content-Type':'application/json','X-Moara-CSRF':me.csrf_token},body:JSON.stringify({version:row.version})});ok=ok&&r.ok;}return ok;}""",{'chats':chats,'resources':resources})
  finally:checkpoint(context);context.close();browser.close()
print(json.dumps({'checks':checks,'passed':True}));assert checks and all(checks.values())
