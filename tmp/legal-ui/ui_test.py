"""Synthetic public-law scenario through the real, isolated browser UI."""
import sys,json,time,hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline());checks={};errors=[];created=[]
def checkpoint(context):
    session=next((c['value'] for c in context.cookies() if c['name']=='__Secure-moara_session'),None)
    if session:Path('/artifacts/moara-legal-ui.json').write_text(json.dumps({'incomplete':True,'created_chats':created,'test_session_sha256':hashlib.sha256(session.encode()).hexdigest()}))
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']])
    context=browser.new_context(viewport={'width':1440,'height':1000})
    context.add_init_script("if(location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
    context.add_init_script("""window.__legalRouting=null;const originalFetch=window.fetch.bind(window);
    window.fetch=async(...args)=>{const response=await originalFetch(...args);
    if(String(args[0]).includes('/moara/api/v1/chat/stream'))response.clone().text().then(text=>{
    for(const line of text.split('\\n'))if(line.startsWith('data: ')){try{const row=JSON.parse(line.slice(6));if(row.moara)window.__legalRouting=row.moara;}catch{}}}).catch(()=>{});
    return response;};""")
    page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)[:200]))
    def response_seen(response):
        if response.request.method=='POST' and response.url.endswith('/moara/api/v1/chats') and response.status==201:
            created.append(response.json()['id']);checkpoint(context)
    page.on('response',response_seen)
    page.goto('https://moara.am.trf1.gov.br/moara/chat',wait_until='networkidle')
    expect(page.get_by_role('heading',name='Como posso ajudar você hoje?')).to_be_visible(timeout=30000)
    checkpoint(context)
    page.get_by_label('Sua mensagem',exact=True).fill('Conferência técnica fictícia: CPC, art. 12; data de referência: 2020-01-01. Não há processo ou pessoa real neste teste.')
    started=time.monotonic();page.get_by_role('button',name='Enviar ↑',exact=True).click()
    expect(page.locator('.message:not(.user-message) .markdown').last).to_contain_text('vigência não confirmada',timeout=90000)
    expect(page.get_by_role('button',name='Gerar novamente',exact=True)).to_be_visible(timeout=15000)
    page.wait_for_function("window.__legalRouting?.legal_verification?.status === 'verification_incomplete'",timeout=15000)
    routing=page.evaluate('window.__legalRouting')
    checks['mandatory_verification_rendered']=True
    checks['conclusions_suspended']=routing['legal_verification']['legal_conclusion_allowed'] is False
    checks['legal_status_visible']=page.get_by_role('status').filter(has_text='Conferência jurídica').count()>0
    checks['excerpts_rendered']=page.locator('.message:not(.user-message) .markdown').last.inner_text().find('preferencialmente')>=0
    elapsed=time.monotonic()-started
    page.locator('.messages').evaluate('(el)=>el.scrollTop=0')
    page.locator('.chat-panel').screenshot(path='/artifacts/moara-legal-chat.png')
    page.get_by_role('link',name='Consultar evidências e fontes',exact=True).click()
    expect(page.get_by_role('heading',name='Evidências da conferência jurídica')).to_be_visible(timeout=30000)
    checks['private_evidence_page_opened']=True
    checks['evidence_export_available']=page.get_by_role('link',name='Baixar registro completo e cópias das fontes').count()==1
    page.screenshot(path='/artifacts/moara-legal-evidence.png')
    removed=page.evaluate("""async ids=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();
    for(const id of ids){const r=await fetch('/moara/api/v1/chats/'+id,{method:'DELETE',headers:{'X-Moara-CSRF':me.csrf_token}});if(!r.ok)return false;}return true;}""",created)
    checks['synthetic_chat_removed']=bool(created) and removed
    checks['no_javascript_errors']=not errors
    session=next(c['value'] for c in context.cookies() if c['name']=='__Secure-moara_session')
    session_hash=hashlib.sha256(session.encode()).hexdigest()
    context.close();browser.close()
report={'checks':checks,'routing':routing,'seconds_from_send_to_rendered_report':elapsed,
        'javascript_errors':errors,'synthetic_only':True,'test_session_sha256':session_hash}
Path('/artifacts/moara-legal-ui.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='test_session_sha256'},ensure_ascii=True),flush=True)
assert all(checks.values())
