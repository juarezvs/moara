"""Exercise the vertical rail and real application-stage SSE in a private browser."""
import sys,json,hashlib,time,re
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline());checks={};chats=list(fixture.get('previous_chats',[]));resources=[];errors=[]
output=Path('/artifacts/brand-ui.json')
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
        page.get_by_role('tab',name='Início',exact=True).click()
        checks['original_background_loaded']=page.evaluate("async()=>{const r=await fetch('/moara/brand/chat-bg.png');return r.ok&&(await r.arrayBuffer()).byteLength>10000;}")
        checks['original_background_applied']='chat-bg.png' in page.locator('.legal-workbench').evaluate('(e)=>getComputedStyle(e).backgroundImage')
        expect(page.get_by_role('heading',name='Como posso ajudar você hoje?')).to_be_visible()
        checks['six_institutional_suggestions']=page.locator('.work-starters button').count()==6
        expect(page.locator('#chat-draft')).to_have_count(1)
        nav=page.get_by_role('navigation',name='Central Moara')
        checks['central_links_are_real_routes']=all((a.get_attribute('href') or '').startswith(('/moara/','/static/moara/')) for a in nav.get_by_role('link').all())
        page.locator('.legal-workbench').screenshot(path='/artifacts/brand-desktop.png',mask=[page.locator('.history-items'),page.locator('.work-dossiers'),page.locator('.work-user')],mask_color='#0b142b')
        page.evaluate("()=>document.documentElement.setAttribute('data-theme','dark')")
        checks['dark_theme_has_light_text']=page.locator('.welcome-question').evaluate("(e)=>getComputedStyle(e).color")=='rgb(237, 244, 255)'
        page.locator('.work-main').screenshot(path='/artifacts/brand-dark.png')
        page.evaluate("()=>document.documentElement.setAttribute('data-theme','light')")
        page.get_by_role('button',name='Analisar documentos Arquivos, trechos e referências rastreáveis',exact=True).click()
        expect(page.locator('.document-dropzone')).to_be_visible();checks['document_suggestion_opens_upload']=True
        page.get_by_role('button',name='Novo trabalho',exact=True).click()
        page.locator('.work-starters button').nth(1).click();expect(page.get_by_role('heading',name='Conferir uma norma',exact=True)).to_be_visible();checks['law_suggestion_opens_reference_form']=True
        page.get_by_role('button',name='Novo trabalho',exact=True).click()
        for index,assistant,mode,term in [(2,'administrativa','Minuta','termo de referência'),(3,'gabinete','Planejar','cronologia'),(4,'desenvolvedora','Planejar','solução'),(5,'dados','Planejar','dados institucionais')]:
            page.locator('.work-starters button').nth(index).click()
            expect(page.get_by_label('Sua mensagem',exact=True)).to_have_value(re.compile('.*'+re.escape(term)+'.*',re.S))
            expect(page.get_by_role('button',name=mode,exact=True)).to_have_attribute('aria-pressed','true')
            page.get_by_role('button',name='Configurar assistente e modelo',exact=True).click()
            expect(page.get_by_label('Assistente',exact=True)).to_have_value(assistant)
            page.get_by_role('button',name='Opções',exact=True).click()
            page.get_by_role('button',name='Novo trabalho',exact=True).click()
        checks['draft_plan_software_and_data_suggestions_configure_real_assistants']=True
        page.get_by_role('tab',name='Documentos',exact=True).click()
        page.locator('input[type=file]').first.set_input_files({'name':'moara-progresso-ficticio.txt','mimeType':'text/plain','buffer':'Registro inteiramente fictício. A equipe deve revisar os arquivos em nove dias úteis. Nenhuma pessoa ou processo real está representado.'.encode()})
        expect(page.get_by_role('status').filter(has_text='Documento pronto e selecionado')).to_be_visible(timeout=150000)
        page.get_by_role('tab',name='Início',exact=True).click()
        page.locator('.work-main').screenshot(path='/artifacts/brand-workspace.png')
        page.get_by_role('button',name='Opções',exact=True).click();page.get_by_label('Assistente',exact=True).select_option('documental');page.get_by_label('Redação',exact=True).select_option('concise');page.get_by_role('button',name='Opções',exact=True).click()
        page.get_by_label('Sua mensagem',exact=True).fill('Resuma o prazo de revisão indicado no documento selecionado e cite a fonte.')
        page.get_by_role('button',name='Enviar solicitação',exact=True).click()
        expect(page.locator('.moara-processing')).to_be_visible(timeout=15000)
        checks['processing_uses_Moara_mark']=page.locator('.processing-mark img').get_attribute('src')=='brand/mark.svg'
        checks['minimal_brand_animation']=page.locator('.processing-mark img').evaluate("(e)=>getComputedStyle(e).animationName.includes('moara-breathe')")
        if not fixture.get('candidate'):expect(page.locator('.processing-copy')).to_contain_text('modelo',timeout=90000)
        expect(page.locator('.message.pending-message')).not_to_be_visible()
        page.locator('.work-main').screenshot(path='/artifacts/brand-processing.png')
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
        page.evaluate('()=>window.scrollTo(0,0)')
        checks['mobile_message_field_is_immediately_available']=page.get_by_label('Sua mensagem',exact=True).evaluate('(e)=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;}')
        page.locator('.work-main').screenshot(path='/artifacts/brand-mobile.png')
        page.evaluate("()=>document.documentElement.classList.add('a11y-large-text')")
        checks['large_text_mobile_no_overflow']=page.evaluate('()=>document.documentElement.scrollWidth<=innerWidth+1')
        page.evaluate("()=>document.documentElement.classList.remove('a11y-large-text')")
        page.evaluate("()=>document.documentElement.classList.add('a11y-high-contrast')")
        checks['high_contrast_removes_background_image']=page.locator('.legal-workbench').evaluate('(e)=>getComputedStyle(e).backgroundImage')=='none'
        checks['high_contrast_rail_icons_are_legible']=page.get_by_role('tab').last.evaluate("(e)=>{const c=document.createElement('canvas').getContext('2d');c.fillStyle=getComputedStyle(e).color;c.fillRect(0,0,1,1);const rgb=Array.from(c.getImageData(0,0,1,1).data).slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});return (.2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2]+.05)/.05>=7;}")
        page.evaluate("()=>document.documentElement.classList.remove('a11y-high-contrast')")

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
