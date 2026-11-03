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
 context=browser.new_context(viewport={'width':1600,'height':1100},has_touch=True);configure(context)
 context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:160]))
 def seen(r):
  if r.request.method=='POST' and r.status==201:
   if r.url.endswith('/moara/api/v1/chats') or re.search('/history/previous/[^/]+/resume$',r.url):chats.append(r.json()['id']);checkpoint(context)
   if r.url.endswith('/moara/api/v1/platform/documents'):resources.append(r.json()['id']);checkpoint(context)
 page.on('response',seen)
 try:
  page.goto('https://moara.am.trf1.gov.br/moara/chat',wait_until='domcontentloaded')
  expect(page.locator('#chat-draft')).to_be_visible(timeout=45000);checkpoint(context)
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
  precedent=fixture_message
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

  checks['no_javascript_errors']=not errors
 finally:
  try:
   checks['synthetic_resources_archived']=page.evaluate("""async({chats,resources})=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();let ok=true;for(const id of chats){const r=await fetch('/moara/api/v1/chats/'+id+'/archive',{method:'POST',headers:{'X-Moara-CSRF':me.csrf_token}});ok=ok&&r.ok;}for(const id of resources){const row=await(await fetch('/moara/api/v1/platform/resources/'+id)).json();const r=await fetch('/moara/api/v1/platform/resources/'+id+'/archive',{method:'POST',headers:{'Content-Type':'application/json','X-Moara-CSRF':me.csrf_token},body:JSON.stringify({version:row.version})});ok=ok&&r.ok;}return ok;}""",{'chats':chats,'resources':resources})
  finally:checkpoint(context);context.close();browser.close()
print(json.dumps({'checks':checks,'passed':True}));assert checks and all(checks.values())
