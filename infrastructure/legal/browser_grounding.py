import sys,json,hashlib
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline());checks={};chats=[];errors=[];evidence_ids=[]
output=Path('/artifacts/legal-grounding-ui.json')
def checkpoint(context):
 token=next((c['value'] for c in context.cookies() if c['name']=='__Secure-moara_session'),None)
 output.write_text(json.dumps({'checks':checks,'created_chats':chats,'evidence_ids':evidence_ids,'test_session_sha256':hashlib.sha256(token.encode()).hexdigest() if token else None,'javascript_errors':errors}))
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']])
 context=browser.new_context(viewport={'width':1500,'height':1100})
 context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
 if fixture.get('candidate'):
  def proxy(route):
   u=urlsplit(route.request.url);r=route.fetch(url='http://'+fixture['candidate']+':8075'+u.path.removeprefix('/moara')+('?' +u.query if u.query else ''),max_redirects=0,timeout=180000);route.fulfill(response=r)
  context.route('https://moara.am.trf1.gov.br/moara/**',proxy)
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:160]))
 def seen(r):
  if r.request.method=='POST' and r.status==201 and r.url.endswith('/moara/api/v1/chats'):chats.append(r.json()['id']);checkpoint(context)
 page.on('response',seen)
 try:
  page.goto('https://moara.am.trf1.gov.br/moara/chat',wait_until='domcontentloaded')
  expect(page.locator('.context-row')).to_have_count(5,timeout=45000);checkpoint(context)
  page.get_by_label('Sua mensagem',exact=True).fill('de acordo com a lei 8112/1990 o que é uma promoção.')
  page.get_by_role('button',name='Enviar solicitação',exact=True).click()
  answer=page.locator('.message:not(.user-message) .markdown').last
  expect(answer).to_contain_text('provimento',timeout=180000);expect(answer).to_contain_text('carreira')
  checks['exact_question_via_real_chat']=True;checks['no_date_clarification']='Você quer considerar' not in answer.inner_text()
  expect(answer).not_to_contain_text('A análise conclusiva foi suspensa');checks['explains_instead_of_blanket_block']=True
  link=page.get_by_role('link',name='Consultar evidências e fontes',exact=True);expect(link).to_be_visible()
  href=link.get_attribute('href');evidence_ids.append(href.rsplit('/',1)[-1])
  value=page.evaluate("async url=>{const r=await fetch(url,{headers:{Accept:'application/json'}});if(!r.ok)throw Error('evidence denied');return r.json();}",href)
  checks['owner_can_review_evidence']=value['integrity']=='stored_manifest_verified' and value['verification']['grounded_response']['status']=='grounded_explanation'
  checks['fresh_sources_audited']=bool(value['verification']['norms'][0]['snapshots']) and value['verification']['reference_date_basis']=='current_date_assumed_for_information'
  checks['no_legal_opinion_bypass']=value['verification']['legal_conclusion_allowed'] is False
  expect(page.locator('.moara-processing')).not_to_be_visible(timeout=90000)
  checks['gpu_grounded_response']=value['verification']['grounded_response']['execution_backend']=='gpu'
  page.locator('.work-main').screenshot(path='/artifacts/legal-grounding-answer.png')
  page.goto('https://moara.am.trf1.gov.br/moara/chat',wait_until='domcontentloaded');expect(page.locator('.context-row')).to_have_count(5,timeout=45000);page.get_by_label('Sua mensagem',exact=True).fill('quais suas habilidades?');page.get_by_role('button',name='Enviar solicitação',exact=True).click()
  expect(page.locator('.message:not(.user-message) .markdown').last).to_contain_text('Moara',timeout=60000);checks['ordinary_capability_question_preserved']=True
  page.goto('https://moara.am.trf1.gov.br/moara/desenvolvimento/api');expect(page.get_by_role('heading',name='API para VS Code',exact=True)).to_be_visible();expect(page.get_by_label('Identificador do modelo')).to_have_value('moara-code');checks['vscode_key_page_preserved']=True
  checks['no_javascript_errors']=not errors
 finally:
  try:
   checks['synthetic_chat_archived']=page.evaluate("""async ids=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();let ok=true;for(const id of ids){const r=await fetch('/moara/api/v1/chats/'+id+'/archive',{method:'POST',headers:{'X-Moara-CSRF':me.csrf_token}});ok=ok&&r.ok;}return ok;}""",chats)
  finally:checkpoint(context);context.close();browser.close()
print(json.dumps({'checks':checks,'errors':errors}));assert checks and all(checks.values())
