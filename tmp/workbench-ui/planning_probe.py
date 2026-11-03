import sys,json,hashlib
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline());checks={};chats=[];errors=[];output=Path('/artifacts/workbench-plan.json')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']])
    context=browser.new_context(viewport={'width':1440,'height':1000})
    context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
    def proxy(route):
        parsed=urlsplit(route.request.url)
        response=route.fetch(url='http://'+fixture['candidate']+':8075'+parsed.path.removeprefix('/moara')+('?' + parsed.query if parsed.query else ''),timeout=180000)
        route.fulfill(response=response)
    context.route('https://moara.am.trf1.gov.br/moara/**',proxy)
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:200]))
    def checkpoint():
        session=next((c['value'] for c in context.cookies() if c['name']=='__Secure-moara_session'),None)
        output.write_text(json.dumps({'checks':checks,'created_chats':chats,'test_session_sha256':hashlib.sha256(session.encode()).hexdigest() if session else None}))
    def response_seen(response):
        if response.request.method=='POST' and response.url.endswith('/moara/api/v1/chats') and response.status==201:chats.append(response.json()['id']);checkpoint()
    page.on('response',response_seen)
    try:
        page.goto('https://moara.am.trf1.gov.br/moara/chat?assistente=juridica',wait_until='networkidle');checkpoint()
        page.get_by_role('button',name='Novo trabalho',exact=True).click()
        page.get_by_role('button',name='Opções',exact=True).click()
        expect(page.get_by_label('Assistente',exact=True)).to_have_value('auto')
        checks['new_work_resets_specialty']=True
        page.get_by_label('Redação',exact=True).select_option('concise');page.get_by_role('button',name='Opções',exact=True).click()
        page.get_by_role('button',name='Planejar',exact=True).click()
        page.get_by_label('Sua mensagem',exact=True).fill('Prepare uma estrutura de comunicação institucional para orientar a revisão de documentos, com destinatário e prazo pendentes.')
        page.get_by_role('button',name='Enviar solicitação',exact=True).click()
        expect(page.get_by_role('button',name='Abrir no editor',exact=True)).to_be_visible(timeout=150000)
        assert 'MODO DE TRABALHO: prepare um roteiro' in page.locator('.user-message').last.inner_text()
        page.get_by_role('button',name='Abrir no editor',exact=True).click()
        page.get_by_label('Rascunho editável',exact=True).fill('Roteiro revisado: destinatário pendente; fluxo de revisão; prazo e responsável como campos pendentes.')
        page.get_by_role('button',name='Usar roteiro na minuta →',exact=True).click()
        expect(page.locator('.context-chip').filter(has_text='Roteiro revisado')).to_be_visible()
        expect(page.get_by_role('button',name='Minuta',exact=True)).to_have_attribute('aria-pressed','true')
        before=page.locator('.message:not(.user-message)').count()
        page.get_by_role('button',name='Enviar solicitação',exact=True).click()
        expect(page.locator('.message:not(.user-message)')).to_have_count(before+1,timeout=150000)
        expect(page.get_by_role('button',name='Abrir no editor',exact=True)).to_be_visible(timeout=150000)
        assert 'ROTEIRO REVISADO PELO USUÁRIO' in page.locator('.user-message').last.inner_text()
        checks['reviewed_plan_precedes_draft']=True
        checks['no_javascript_errors']=not errors
    finally:
        try:
            checks['synthetic_chats_archived']=page.evaluate("""async ids=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();let ok=true;for(const id of ids){const r=await fetch('/moara/api/v1/chats/'+id+'/archive',{method:'POST',headers:{'X-Moara-CSRF':me.csrf_token}});ok=ok&&r.ok;}return ok;}""",chats)
        finally:checkpoint();context.close();browser.close()
print(json.dumps({'checks':checks,'errors':errors}));assert all(checks.values())
