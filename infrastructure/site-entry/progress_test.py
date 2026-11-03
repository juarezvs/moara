"""Exercise the vertical rail and real application-stage SSE in a private browser."""
import sys,json,hashlib,time
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline());checks={};chats=list(fixture.get('previous_chats',[]));resources=[];errors=[]
output=Path('/artifacts/work-progress-ui.json')
def checkpoint(context):
    token=next((c['value'] for c in context.cookies() if c['name']=='__Secure-moara_session'),None)
    output.write_text(json.dumps({'checks':checks,'created_chats':chats,'created_resources':resources,'test_session_sha256':hashlib.sha256(token.encode()).hexdigest() if token else None,'javascript_errors':errors}))
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']])
    context=browser.new_context(viewport={'width':1600,'height':1100})
    context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
    context.add_init_script("""window.__stages=[];window.__meta=null;const f=window.fetch.bind(window);window.fetch=async(...args)=>{const r=await f(...args);if(String(args[0]).includes('/moara/api/v1/chat/stream')){window.__stages=[];window.__meta=null;(async()=>{const reader=r.clone().body.getReader(),decoder=new TextDecoder();let pending='';while(true){const {value,done}=await reader.read();if(done)break;pending+=decoder.decode(value,{stream:true});let n;while((n=pending.indexOf('\\n'))>=0){const line=pending.slice(0,n);pending=pending.slice(n+1);if(line.startsWith('data: ')){try{const v=JSON.parse(line.slice(6));if(v.moara_progress)window.__stages.push(v.moara_progress.stage);if(v.moara)window.__meta=v.moara;}catch{}}}}})().catch(()=>{});}return r;};""")
    if fixture.get('candidate'):
        def proxy(route):
            u=urlsplit(route.request.url)
            response=route.fetch(url='http://'+fixture['candidate']+':8075'+u.path.removeprefix('/moara')+('?' +u.query if u.query else ''),max_redirects=0,timeout=180000)
            route.fulfill(response=response)
        context.route('https://moara.am.trf1.gov.br/moara/**',proxy)
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:160]))
    def response_seen(r):
        if r.request.method=='POST' and r.status==201:
            if r.url.endswith('/moara/api/v1/chats'):chats.append(r.json()['id']);checkpoint(context)
            if r.url.endswith('/moara/api/v1/platform/documents'):resources.append(r.json()['id']);checkpoint(context)
    page.on('response',response_seen)
    try:
        page.goto('https://moara.am.trf1.gov.br/moara/chat',wait_until='domcontentloaded')
        expect(page.locator('.context-row')).to_have_count(5,timeout=45000);checkpoint(context)
        tabs=page.get_by_role('tab');boxes=[tabs.nth(i).bounding_box() for i in range(6)]
        body=page.locator('.work-body').bounding_box()
        checks['six_tabs_vertical_on_right']=all(abs(b['x']-boxes[0]['x'])<2 for b in boxes) and all(boxes[i+1]['y']>boxes[i]['y'] for i in range(5)) and boxes[0]['x']>=body['x']+body['width']
        expect(page.get_by_role('tablist')).to_have_attribute('aria-orientation','vertical')
        tabs.first.focus();page.keyboard.press('ArrowDown');expect(tabs.nth(1)).to_be_focused();checks['vertical_keyboard_navigation']=True
        page.get_by_role('tab',name='Documentos',exact=True).click()
        page.locator('input[type=file]').first.set_input_files({'name':'moara-progresso-ficticio.txt','mimeType':'text/plain','buffer':'Registro inteiramente fictício. A equipe deve revisar os arquivos em nove dias úteis. Nenhuma pessoa ou processo real está representado.'.encode()})
        expect(page.get_by_role('status').filter(has_text='Documento pronto e selecionado')).to_be_visible(timeout=150000)
        page.get_by_role('tab',name='Início',exact=True).click()
        page.locator('.work-main').screenshot(path='/artifacts/work-progress-rail.png')
        page.get_by_role('button',name='Opções',exact=True).click();page.get_by_label('Assistente',exact=True).select_option('documental');page.get_by_label('Redação',exact=True).select_option('concise');page.get_by_role('button',name='Opções',exact=True).click()
        page.get_by_label('Sua mensagem',exact=True).fill('Resuma o prazo de revisão indicado no documento selecionado e cite a fonte.')
        page.get_by_role('button',name='Enviar solicitação',exact=True).click()
        expect(page.locator('.moara-processing')).to_be_visible(timeout=15000)
        checks['processing_uses_Moara_mark']=page.locator('.processing-mark img').get_attribute('src')=='brand/mark.svg'
        checks['minimal_brand_animation']=page.locator('.processing-mark img').evaluate("(e)=>getComputedStyle(e).animationName.includes('moara-breathe')")
        if not fixture.get('candidate'):expect(page.locator('.processing-copy')).to_contain_text('modelo',timeout=90000)
        expect(page.locator('.message.pending-message')).not_to_be_visible()
        page.locator('.work-main').screenshot(path='/artifacts/work-progress-processing.png')
        expect(page.get_by_role('button',name='Abrir no editor',exact=True)).to_be_visible(timeout=150000)
        stages=page.evaluate('()=>window.__stages')
        checks['real_document_stages']=all(s in stages for s in ['analyzing_request','retrieving_documents','generating_response','checking_response'])
        checks['no_invented_legal_research']='checking_legal_sources' not in stages
        checks['model_ran_on_GPU']=page.evaluate("()=>window.__meta?.execution_backend==='gpu'")
        checks['answer_keeps_document_citations']='[D' in page.locator('.message:not(.user-message) .markdown').last.inner_text()
        expect(page.locator('.moara-processing')).not_to_be_visible();checks['processing_finishes']=True
        page.get_by_role('button',name='Novo trabalho',exact=True).click()
        page.get_by_role('tab',name='Referências',exact=True).click()
        page.locator('input[name=reference-norm]').fill('CPC');page.locator('input[name=reference-article]').fill('art. 12');page.locator('input[name=reference-date]').fill('2020-01-01')
        page.get_by_role('button',name='Conferir fontes oficiais',exact=True).click()
        expect(page.get_by_role('link',name='Consultar evidências e fontes',exact=True)).to_be_visible(timeout=150000)
        checks['real_legal_lookup_stage']='checking_legal_sources' in page.evaluate('()=>window.__stages')
        checks['legal_confirmation_limits_preserved']=page.evaluate('()=>window.__meta?.legal_verification?.legal_conclusion_allowed===false')
        page.get_by_role('button',name='Novo trabalho',exact=True).click()
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(400)
        checks['mobile_no_overflow']=page.evaluate('()=>document.documentElement.scrollWidth<=innerWidth+1')
        box=page.get_by_role('tab').first.bounding_box();checks['mobile_rail_is_right']=box['x']>300
        page.locator('.work-main').screenshot(path='/artifacts/work-progress-mobile.png')
        page.evaluate("()=>document.documentElement.classList.add('a11y-large-text')")
        checks['large_text_mobile_no_overflow']=page.evaluate('()=>document.documentElement.scrollWidth<=innerWidth+1')
        page.evaluate("()=>document.documentElement.classList.remove('a11y-large-text')")
        page.emulate_media(reduced_motion='reduce')
        page.get_by_label('Sua mensagem',exact=True).fill('Prepare uma lista detalhada de vinte etapas para organizar arquivos digitais fictícios.')
        page.get_by_role('button',name='Enviar solicitação',exact=True).click()
        expect(page.locator('.moara-processing')).to_be_visible()
        checks['reduced_motion_respected']=page.locator('.processing-mark img').evaluate('(e)=>getComputedStyle(e).animationName')=='none'
        if not fixture.get('candidate'):expect(page.locator('.processing-copy')).to_contain_text('modelo',timeout=90000)
        page.get_by_role('button',name='Interromper',exact=True).click()
        expect(page.locator('.moara-processing')).not_to_be_visible(timeout=30000);checks['cancel_clears_processing']=True
        checks['no_javascript_errors']=not errors
    finally:
        try:
            checks['synthetic_chat_archived']=page.evaluate("""async ({chats,resources})=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();let ok=true;for(const id of chats){const r=await fetch('/moara/api/v1/chats/'+id+'/archive',{method:'POST',headers:{'X-Moara-CSRF':me.csrf_token}});ok=ok&&r.ok;}for(const id of resources){const row=await(await fetch('/moara/api/v1/platform/resources/'+id)).json();const r=await fetch('/moara/api/v1/platform/resources/'+id+'/archive',{method:'POST',headers:{'Content-Type':'application/json','X-Moara-CSRF':me.csrf_token},body:JSON.stringify({version:row.version})});ok=ok&&r.ok;}return ok;}""",{'chats':chats,'resources':resources})
        finally:checkpoint(context);context.close();browser.close()
print(json.dumps({'checks':checks,'errors':errors}));assert checks and all(checks.values())
