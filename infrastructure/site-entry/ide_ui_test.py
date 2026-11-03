import sys,json,hashlib,io,zipfile,time,base64
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline());checks={};errors=[];created=[];keyname='IDE browser synthetic '+str(time.time_ns())
output=Path('/artifacts/ide-ui.json')
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']])
 context=browser.new_context(viewport={'width':1500,'height':1100})
 context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
 if fixture.get('candidate'):
  def proxy(route):
   u=urlsplit(route.request.url);r=route.fetch(url='http://'+fixture['candidate']+':8075'+u.path.removeprefix('/moara')+('?' +u.query if u.query else ''),max_redirects=0,timeout=180000);route.fulfill(response=r)
  context.route('https://moara.am.trf1.gov.br/moara/**',proxy)
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:160]))
 def save():
  token=next((c['value'] for c in context.cookies() if c['name']=='__Secure-moara_session'),None)
  output.write_text(json.dumps({'checks':checks,'test_key_ids':created,'test_session_sha256':hashlib.sha256(token.encode()).hexdigest() if token else None,'javascript_errors':errors},indent=2))
 def response_seen(r):
  if r.request.method=='POST' and r.status==201 and r.url.endswith('/developer/keys'):created.append(r.json()['id']);save()
 page.on('response',response_seen)
 try:
  page.goto('https://moara.am.trf1.gov.br/moara/desenvolvimento/api',wait_until='domcontentloaded')
  expect(page.get_by_role('heading',name='API para VS Code',exact=True)).to_be_visible(timeout=45000);save()
  expect(page.get_by_label('URL base da API')).to_have_value('https://moara.am.trf1.gov.br/moara/v1')
  expect(page.get_by_label('Identificador do modelo')).to_have_value('moara-code');checks['connection_fields']=True
  page.get_by_role('button',name='Criar chave pessoal',exact=True).click();page.get_by_label('Nome da chave').fill(keyname)
  page.get_by_role('button',name='Gerar chave pessoal',exact=True).click();dialog=page.get_by_role('dialog')
  expect(dialog).to_be_visible();secret=page.get_by_label('Chave API',exact=True).input_value();assert secret.startswith('moara_');checks['ui_create_key']=True
  page.keyboard.press('Escape');expect(dialog).not_to_be_visible();assert secret not in page.content();checks['secret_removed_after_close']=True
  with page.expect_download() as d:page.get_by_role('link',name='Baixar configura\u00e7\u00e3o do Continue').click()
  download=d.value;assert download.suggested_filename=='moara-vscode-continue.zip'
  if fixture.get('candidate'):
   raw=page.evaluate("async()=>{const r=await fetch('/moara/api/v1/developer/continue.zip');if(!r.ok)throw Error('bundle failed');return btoa(String.fromCharCode(...new Uint8Array(await r.arrayBuffer())))}")
   data=io.BytesIO(base64.b64decode(raw))
  else:data=download.path()
  with zipfile.ZipFile(data) as z:assert all(secret.encode() not in z.read(n) for n in z.namelist())
  checks['browser_download_no_secret']=True
  page.screenshot(path='/artifacts/ide-desktop.png',mask=[page.locator('tbody'),page.locator('.user-menu')])
  row=page.get_by_role('row').filter(has_text=keyname);expect(row).to_have_count(1)
  row.get_by_role('button',name='Revogar',exact=True).click();page.get_by_role('button',name='Confirmar revoga\u00e7\u00e3o',exact=True).click()
  expect(row).to_contain_text('Revogada');checks['ui_revoke_key']=True
  status=page.evaluate("async(key)=>(await fetch('/moara/v1/models',{headers:{Authorization:'Bearer '+key}})).status",secret);assert status==401;checks['revocation_denies_access']=True
  page.set_viewport_size({'width':390,'height':844});page.screenshot(path='/artifacts/ide-mobile.png',mask=[page.locator('tbody')])
  checks['mobile_no_document_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
  page.goto('https://moara.am.trf1.gov.br/moara/chat');expect(page.locator('.context-row')).to_have_count(5,timeout=45000);checks['chat_preserved']=True
  checks['no_javascript_errors']=not errors
 finally:
  # Native browser API, never logout the real user's legacy account.
  page.evaluate("""async(ids)=>{const m=await fetch('/moara/api/v1/auth/me').then(r=>r.json());for(const id of ids)await fetch('/moara/api/v1/developer/keys/'+id+'/revoke',{method:'POST',headers:{'x-moara-csrf':m.csrf_token}})}""",created)
  save()
 browser.close()
assert all(checks.values()),checks
print(json.dumps({'checks':checks,'passed':True}))
