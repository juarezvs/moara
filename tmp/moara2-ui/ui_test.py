"""Isolated candidate UI acceptance; only synthetic content is created."""
import sys,json,time,hashlib
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline());checks={};errors=[];created=[];documents=[]
output=Path('/artifacts/moara2-ui.json')
def checkpoint(context):
    session=next((c['value'] for c in context.cookies() if c['name']=='__Secure-moara_session'),None)
    output.write_text(json.dumps({'checks':checks,'created_chats':created,'created_documents':documents,
        'test_session_sha256':hashlib.sha256(session.encode()).hexdigest() if session else None}))
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']])
    context=browser.new_context(viewport={'width':1440,'height':1100})
    context.add_init_script("if(window===window.top && location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
    context.add_init_script("""window.__moaraMetadata=null;const originalFetch=window.fetch.bind(window);window.fetch=async(...args)=>{const response=await originalFetch(...args);if(String(args[0]).includes('/moara/api/v1/chat/stream'))response.clone().text().then(text=>{for(const line of text.split('\\n'))if(line.startsWith('data: ')){try{const value=JSON.parse(line.slice(6));if(value.moara)window.__moaraMetadata=value.moara;}catch{}}});return response;};""")
    if fixture.get('candidate'):
        def proxy(route):
            parsed=urlsplit(route.request.url)
            target='http://'+fixture['candidate']+':8075'+parsed.path.removeprefix('/moara')+('?' + parsed.query if parsed.query else '')
            response=route.fetch(url=target,timeout=180000);route.fulfill(response=response)
        context.route('https://moara.am.trf1.gov.br/moara/**',proxy)
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:200]))
    def response_seen(response):
        if response.request.method=='POST' and response.status==201:
            if response.url.endswith('/moara/api/v1/chats'):created.append(response.json()['id']);checkpoint(context)
            if response.url.endswith('/moara/api/v1/platform/documents'):documents.append(response.json()['id']);checkpoint(context)
    page.on('response',response_seen)
    try:
        page.goto('https://moara.am.trf1.gov.br/moara/chat',wait_until='networkidle');checkpoint(context)
        expect(page.locator('.assistant-card')).to_have_count(6,timeout=30000);checks['six_cards']=True
        page.locator('.assistant-card').filter(has_text='Moara Documental').click()
        page.locator('details').filter(has=page.locator('input[type=file]')).locator('summary').click()
        page.locator('input[type=file]').set_input_files({'name':'validacao-interface-moara2.txt','mimeType':'text/plain',
            'buffer':'Documento sintético de homologação. O prazo interno fictício de revisão é de nove dias úteis. Não contém dados reais.'.encode()})
        expect(page.get_by_role('status').filter(has_text='Documento pronto e selecionado')).to_be_visible(timeout=150000)
        checks['upload_indexed']=True
        page.get_by_label('Sua mensagem',exact=True).fill('Qual é o prazo interno de revisão no documento fornecido? Cite a fonte e não acrescente normas.')
        started=time.monotonic();page.get_by_role('button',name='Enviar ↑',exact=True).click()
        expect(page.get_by_role('button',name='Gerar novamente',exact=True)).to_be_visible(timeout=150000)
        answer=page.locator('.message:not(.user-message) .markdown').last.inner_text()
        assert ('nove' in answer.lower() or '9' in answer) and '[D1]' in answer,answer[:200]
        checks['rag_answer_cited']=True;checks['seconds_send_to_answer']=round(time.monotonic()-started,2)
        page.wait_for_function("window.__moaraMetadata?.execution_backend==='gpu'",timeout=15000)
        checks['gpu_backend_confirmed']=True
        page.locator('.chat-panel').screenshot(path='/artifacts/moara2-chat.png')
        page.reload(wait_until='networkidle');page.locator('.history-item').filter(has_text='Qual é o prazo interno de revisão no documento fornecido?').first.click()
        expect(page.locator('.message:not(.user-message) .markdown').last).to_contain_text('[D1]');checks['history_reopens']=True
        page.get_by_role('button',name='Preferências de acessibilidade',exact=True).click()
        dialog=page.get_by_role('dialog');expect(dialog).to_be_visible()
        dialog.get_by_label('Tamanho do texto').select_option(label='130%')
        dialog.get_by_label('Alto contraste',exact=True).check();dialog.get_by_label('Fonte OpenDyslexic',exact=True).check()
        assert page.evaluate("document.documentElement.classList.contains('a11y-high-contrast') && document.documentElement.classList.contains('a11y-dyslexic')")
        page.evaluate("document.fonts.load('16px OpenDyslexic')")
        assert page.evaluate("document.fonts.check('16px OpenDyslexic')")
        checks['local_font_contrast_scale']=True
        page.keyboard.press('Escape');expect(dialog).not_to_be_visible();checks['escape_closes_dialog']=True
        page.get_by_role('button',name='Preferências de acessibilidade',exact=True).click();page.get_by_role('button',name='Restaurar preferências',exact=True).click();page.keyboard.press('Escape')
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(400)
        checks['mobile_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
        page.locator('.chat-panel').screenshot(path='/artifacts/moara2-chat-mobile.png')
        page.set_viewport_size({'width':1440,'height':1100})
        page.goto('https://moara.am.trf1.gov.br/moara/assistentes',wait_until='networkidle')
        expect(page.locator('a[href="https://sei.trf1.jus.br/"]')).to_be_visible(timeout=15000)
        expect(page.locator('a[href="https://pje1g.trf1.jus.br/"]')).to_be_visible()
        checks['prepared_integrations_visible_in_admin']=True
        page.goto('https://moara.am.trf1.gov.br/moara/',wait_until='networkidle')
        expect(page.get_by_role('heading',name='Servidor de inferência GPU',exact=True)).to_be_visible(timeout=15000)
        if not fixture.get('candidate'):
            expect(page.get_by_text('TLS com autenticação mútua e túnel SSH',exact=False)).to_be_visible(timeout=15000)
            expect(page.get_by_text('VRAM física:',exact=False)).to_be_visible()
            checks['physical_GPU_metrics_visible']=True
        page.goto('https://moara.am.trf1.gov.br/moara/sobre',wait_until='networkidle')
        page.get_by_role('button',name='Ativar VLibras para o manifesto público',exact=True).click()
        frame=page.frame_locator('iframe.public-libras-frame')
        expect(frame.locator('body')).to_contain_text('Moara',timeout=30000)
        expect(frame.locator('#vlibras-button')).to_be_attached(timeout=30000)
        child=next(f for f in page.frames if '/accessibility/libras' in f.url)
        checks['libras_parent_isolated']=child.evaluate("(()=>{try{parent.document.body;return false}catch{return true}})()")
        checks['libras_cookie_isolated']=child.evaluate("(()=>{try{return document.cookie===''}catch{return true}})()")
        checks['public_libras_widget_loaded']=True
        checks['no_javascript_errors']=not errors
    finally:
        try:
            result=page.evaluate("""async ({chats,documents})=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();let ok=true;
            for(const id of chats){const r=await fetch('/moara/api/v1/chats/'+id+'/archive',{method:'POST',headers:{'X-Moara-CSRF':me.csrf_token}});ok=ok&&r.ok;}
            for(const id of documents){const resource=await(await fetch('/moara/api/v1/platform/resources/'+id)).json();const r=await fetch('/moara/api/v1/platform/resources/'+id+'/archive',{method:'POST',headers:{'Content-Type':'application/json','X-Moara-CSRF':me.csrf_token},body:JSON.stringify({version:resource.version})});ok=ok&&r.ok;}
            return ok;}""",{'chats':created,'documents':documents})
            checks['synthetic_content_archived']=result
        finally:checkpoint(context);context.close();browser.close()
report=json.loads(output.read_text());report['javascript_errors']=errors;report['candidate_proxy']=bool(fixture.get('candidate'));output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'checks':checks,'javascript_errors':errors},ensure_ascii=True),flush=True)
assert all(checks.values())
