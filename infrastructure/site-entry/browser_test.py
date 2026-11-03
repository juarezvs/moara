"""Check canonical entry, real session bridge and preserved legacy UI."""
import sys,json,hashlib,time
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline());checks={};chats=list(fixture.get('previous_chats',[]));errors=[]
output=Path('/artifacts/primary-entry-ui.json')
def proxy(route):
    u=urlsplit(route.request.url)
    response=route.fetch(url='http://'+fixture['candidate']+':8080'+u.path+('?' +u.query if u.query else ''),max_redirects=0,timeout=180000)
    route.fulfill(response=response)
def configure(context):
    if fixture.get('candidate'):context.route('https://moara.am.trf1.gov.br/**',proxy)
def checkpoint(context):
    session=next((c['value'] for c in context.cookies() if c['name']=='__Secure-moara_session'),None)
    output.write_text(json.dumps({'checks':checks,'created_chats':chats,'test_session_sha256':hashlib.sha256(session.encode()).hexdigest() if session else None,'javascript_errors':errors}))
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']])
    anonymous=browser.new_context(viewport={'width':1440,'height':1000});configure(anonymous)
    page=anonymous.new_page()
    if fixture.get('candidate'):
        r=anonymous.request.get('http://'+fixture['candidate']+':8080/',max_redirects=0)
        assert r.status==302 and r.headers['location']=='/moara/chat'
        checks['stage_root_redirect_validated']=True
    entry='https://moara.am.trf1.gov.br/moara/chat' if fixture.get('candidate') else 'https://moara.am.trf1.gov.br/'
    page.goto(entry,wait_until='domcontentloaded')
    expect(page.get_by_role('heading',name='Entre na Moara')).to_be_visible(timeout=30000)
    checks['anonymous_root_opens_institutional_login']=('/moara/login' in page.url and 'returnTo=' in page.url)
    expect(page.locator('.large-brand img')).to_be_visible()
    checks['login_keeps_Moara_identity']=page.locator('.large-brand img').evaluate('(e)=>e.complete&&e.naturalWidth>0')
    expect(page.locator('a.institutional-login')).to_have_attribute('href','/?interface=anterior')
    page.screenshot(path='/artifacts/primary-entry-login.png')
    page.locator('a.institutional-login').click()
    page.wait_for_url('**/auth**',timeout=45000)
    checks['alternative_authentication_has_no_redirect_loop']=True
    anonymous.close()
    context=browser.new_context(viewport={'width':1600,'height':1100});configure(context)
    context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
    context.add_init_script("""window.__entryMeta=null;const efetch=window.fetch.bind(window);window.fetch=async(...args)=>{const r=await efetch(...args);if(String(args[0]).includes('/moara/api/v1/chat/stream'))r.clone().text().then(t=>{for(const l of t.split('\\n'))if(l.startsWith('data: ')){try{const v=JSON.parse(l.slice(6));if(v.moara)window.__entryMeta=v.moara;}catch{}}});return r;};""")
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:180]))
    def response_seen(response):
        if response.request.method=='POST' and response.status==201 and response.url.endswith('/moara/api/v1/chats'):
            chats.append(response.json()['id']);checkpoint(context)
    page.on('response',response_seen)
    try:
        page.goto(entry,wait_until='domcontentloaded')
        expect(page.locator('.context-row')).to_have_count(5,timeout=45000);checkpoint(context)
        checks['authenticated_root_opens_workbench']=page.url=='https://moara.am.trf1.gov.br/moara/chat'
        checks['six_workspace_tabs']=page.get_by_role('tab').count()==6
        page.locator('.work-main').screenshot(path='/artifacts/primary-entry-workbench.png')
        page.get_by_label('Sua mensagem',exact=True).fill('quais suas habilidades?')
        page.get_by_role('button',name='Enviar solicitação',exact=True).click()
        answer=page.locator('.message:not(.user-message) .markdown').last
        expect(answer).to_contain_text('Moara',timeout=90000)
        checks['capabilities_answer_is_not_blocked_by_legal_date']='informe a data relevante' not in answer.inner_text().lower()
        page.get_by_label('Sua mensagem',exact=True).fill('Reescreva em uma frase clara e objetiva: A equipe procederá à organização dos arquivos amanhã.')
        start=time.monotonic();page.get_by_role('button',name='Enviar solicitação',exact=True).click()
        for _ in range(500):
            if page.evaluate("()=>window.__entryMeta?.execution_backend==='gpu'"):break
            page.wait_for_timeout(300)
        else:raise AssertionError('GPU response metadata not received')
        checks['real_model_response_on_GPU']=True
        checks['model_response_seconds']=round(time.monotonic()-start,2)
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(400)
        checks['mobile_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.set_viewport_size({'width':1600,'height':1100})
        checks['synthetic_chat_archived']=page.evaluate("""async ids=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();for(const id of ids){const r=await fetch('/moara/api/v1/chats/'+id+'/archive',{method:'POST',headers:{'X-Moara-CSRF':me.csrf_token}});if(!r.ok)return false;}return true;}""",chats)
        checkpoint(context)
        legacy='https://moara.am.trf1.gov.br/?interface=anterior' if fixture.get('candidate') else 'https://moara.am.trf1.gov.br/chat-anterior'
        page.goto(legacy,wait_until='domcontentloaded')
        expect(page.locator('#chat-input')).to_be_visible(timeout=45000)
        checks['legacy_chat_remains_available']='interface=anterior' in page.url
        checks['brand_assets_preserved']=page.evaluate("async()=>{const r=await fetch('/moara/brand/mark.svg');return r.ok&&(await r.text()).includes('<svg');}")
        page.goto('https://moara.am.trf1.gov.br/moara/chat',wait_until='domcontentloaded')
        expect(page.locator('.context-row')).to_have_count(5,timeout=30000)
        checks['canonical_chat_still_works']=True
        checks['no_javascript_errors']=not errors
    finally:
        checkpoint(context);context.close();browser.close()
print(json.dumps({'checks':checks,'errors':errors}))
assert checks and all(checks.values())
