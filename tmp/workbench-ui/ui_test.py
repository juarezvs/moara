"""Exercise the actual institutional workspace with synthetic files/resources."""
import sys,json,time,hashlib
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline());checks={};errors=[];chats=[];resources=[];source_ids=[]
output=Path('/artifacts/workbench-ui.json')
def checkpoint(context):
    session=next((c['value'] for c in context.cookies() if c['name']=='__Secure-moara_session'),None)
    output.write_text(json.dumps({'checks':checks,'created_chats':chats,'created_resources':resources,
        'test_session_sha256':hashlib.sha256(session.encode()).hexdigest() if session else None}))
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']])
    context=browser.new_context(viewport={'width':1600,'height':1100},accept_downloads=True)
    context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
    context.add_init_script("""window.__workMeta=null;const originalFetch=window.fetch.bind(window);window.fetch=async(...args)=>{const response=await originalFetch(...args);if(String(args[0]).includes('/moara/api/v1/chat/stream'))response.clone().text().then(text=>{for(const line of text.split('\\n'))if(line.startsWith('data: ')){try{const value=JSON.parse(line.slice(6));if(value.moara)window.__workMeta=value.moara;}catch{}}});return response;};""")
    if fixture.get('candidate'):
        def proxy(route):
            parsed=urlsplit(route.request.url)
            response=route.fetch(url='http://'+fixture['candidate']+':8075'+parsed.path.removeprefix('/moara')+('?' + parsed.query if parsed.query else ''),timeout=180000)
            route.fulfill(response=response)
        context.route('https://moara.am.trf1.gov.br/moara/**',proxy)
    page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)[:220]))
    def response_seen(response):
        if response.request.method=='POST' and response.status==201:
            if response.url.endswith('/moara/api/v1/chats'):chats.append(response.json()['id']);checkpoint(context)
            if response.url.endswith('/moara/api/v1/platform/documents'):
                identifier=response.json()['id'];resources.append(identifier);source_ids.append(identifier);checkpoint(context)
            if response.url.endswith('/moara/api/v1/platform/resources'):resources.append(response.json()['id']);checkpoint(context)
    page.on('response',response_seen)
    try:
        page.goto('https://moara.am.trf1.gov.br/moara/chat',wait_until='networkidle');checkpoint(context)
        expect(page.locator('.context-row')).to_have_count(5,timeout=30000)
        checks['five_context_actions']=True
        page.locator('.work-main').screenshot(path='/artifacts/workbench-start.png')
        page.get_by_role('tab',name='Início',exact=True).focus();page.keyboard.press('ArrowRight')
        expect(page.get_by_role('heading',name='Histórico de trabalho',exact=True)).to_be_visible();checks['keyboard_tab_navigation']=True
        page.get_by_role('tab',name='Documentos',exact=True).click()
        data=page.evaluate_handle("""()=>{const data=new DataTransfer();data.items.add(new File(['Arquivo inteiramente fictício. O prazo interno de revisão é de nove dias úteis. Não há pessoas ou processos reais.'],'workbench-validacao-ficticia.txt',{type:'text/plain'}));return data;}""")
        page.locator('.document-dropzone').dispatch_event('drop',{'dataTransfer':data})
        expect(page.get_by_role('status').filter(has_text='Documento pronto e selecionado')).to_be_visible(timeout=150000)
        checks['drag_drop_indexed_and_selected']=True
        page.get_by_role('button',name='T Inserir texto',exact=True).click()
        page.locator('input[name=paste-title]').fill('workbench-texto-ficticio')
        page.locator('textarea[name=paste-content]').fill('Registro sintético de apoio: a unidade fictícia revisa o material em nove dias úteis.')
        page.get_by_role('button',name='Salvar e indexar texto',exact=True).click()
        expect(page.locator('.paste-document')).not_to_be_visible(timeout=150000)
        expect(page.locator('.document-item input:checked')).to_have_count(2)
        checks['pasted_text_persisted_and_indexed']=True
        page.locator('.document-dropzone').screenshot(path='/artifacts/workbench-documents.png')
        page.get_by_role('tab',name='Acervo',exact=True).click();page.get_by_role('button',name='Modelos',exact=True).click()
        page.locator('input[name=library-title]').fill('WB — modelo sintético de relatório')
        page.locator('textarea[name=library-text]').fill('# Relatório interno\n\n## Prazo informado\nDescrever somente o prazo presente nos documentos, com citação.\n\n## Pendências\nRegistrar o que não foi informado.')
        page.get_by_role('button',name='Salvar no acervo',exact=True).click()
        expect(page.locator('.library-item').filter(has_text='WB — modelo sintético de relatório')).to_be_visible(timeout=20000)
        checks['reusable_template_saved']=True
        page.get_by_role('tab',name='Modelos',exact=True).click()
        page.locator('.resource-card').filter(has_text='WB — modelo sintético de relatório').get_by_role('button',name='Usar como estrutura').click()
        expect(page.locator('.context-chip').filter(has_text='WB — modelo sintético de relatório')).to_be_visible()
        checks['template_selected_as_context']=True
        page.get_by_role('tab',name='Acervo',exact=True).click();page.get_by_role('button',name='Instruções',exact=True).click()
        page.locator('input[name=library-title]').fill('WB — instrução sintética')
        page.locator('textarea[name=library-text]').fill('Qual é o prazo interno de revisão indicado nos documentos selecionados? Cite as fontes e preserve as pendências.')
        page.get_by_role('button',name='Salvar no acervo',exact=True).click()
        row=page.locator('.library-item').filter(has_text='WB — instrução sintética');expect(row).to_be_visible(timeout=20000)
        row.get_by_role('button',name='Usar no trabalho →').click();checks['saved_prompt_applied']=True
        page.get_by_role('button',name='Opções',exact=True).click()
        page.get_by_label('Assistente',exact=True).select_option('documental')
        page.get_by_label('Redação',exact=True).select_option('concise')
        page.get_by_role('button',name='Opções',exact=True).click()
        start=time.monotonic();page.get_by_role('button',name='Enviar solicitação',exact=True).click()
        expect(page.get_by_role('button',name='Abrir no editor',exact=True)).to_be_visible(timeout=150000)
        answer=page.locator('.message:not(.user-message) .markdown').last.inner_text()
        assert ('nove' in answer.lower() or '9' in answer) and '[D' in answer,answer[:150]
        page.wait_for_function("window.__workMeta?.execution_backend==='gpu'")
        checks['cited_RAG_draft_on_GPU']=True;checks['seconds_for_draft']=round(time.monotonic()-start,2)
        checks['template_snapshot_in_history']=page.locator('.user-message').last.inner_text().find('MODELO DE ESTRUTURA')>=0
        page.get_by_role('button',name='Abrir no editor',exact=True).click()
        page.get_by_label('Título do documento',exact=True).fill('WB rascunho sintético revisado')
        page.get_by_label('Rascunho editável',exact=True).fill('Revisão humana sintética. Prazo informado: nove dias úteis. Este documento é apenas um teste de interface.')
        with page.expect_download() as download_info:page.get_by_role('button',name='Baixar rascunho .md',exact=True).click()
        download=download_info.value
        assert download.suggested_filename.endswith('.md') and 'RASCUNHO' in Path(download.path()).read_text()
        checks['edited_draft_downloaded']=True
        page.get_by_role('button',name='Salvar como documento',exact=True).click()
        expect(page.get_by_role('status').filter(has_text='Rascunho salvo como documento')).to_be_visible(timeout=20000)
        checks['edited_draft_persisted']=True
        page.locator('.work-main').screenshot(path='/artifacts/workbench-editor.png')
        page.get_by_role('button',name='Voltar à conversa',exact=True).click()
        assert 'Revisão humana sintética' not in page.locator('.message:not(.user-message) .markdown').last.inner_text()
        checks['original_answer_preserved']=True
        page.get_by_role('tab',name='Acervo',exact=True).click();page.get_by_role('button',name='Dossiês',exact=True).click()
        page.locator('input[name=library-title]').fill('WB — dossiê fictício')
        page.locator('textarea[name=library-text]').fill('Organizar a revisão dos documentos fictícios selecionados.')
        page.get_by_role('button',name='Salvar no acervo',exact=True).click()
        expect(page.locator('.library-item').filter(has_text='WB — dossiê fictício')).to_be_visible(timeout=20000)
        page.locator('.library-item').filter(has_text='WB — dossiê fictício').get_by_role('button',name='Abrir dossiê →').click()
        expect(page.locator('.context-chip')).to_have_count(2)
        checks['dossier_restores_document_selection']=True
        page.get_by_role('tab',name='Referências',exact=True).click()
        page.locator('input[name=reference-norm]').fill('CPC');page.locator('input[name=reference-article]').fill('art. 12');page.locator('input[name=reference-date]').fill('2020-01-01')
        page.get_by_role('button',name='Conferir fontes oficiais',exact=True).click()
        expect(page.get_by_role('link',name='Consultar evidências e fontes',exact=True)).to_be_visible(timeout=120000)
        page.wait_for_function("window.__workMeta?.legal_verification?.legal_conclusion_allowed===false")
        checks['legal_form_runs_mandatory_preflight']=True
        page.get_by_role('button',name='Novo trabalho',exact=True).click()
        page.get_by_role('button',name='Planejar',exact=True).click()
        page.get_by_role('button',name='Opções',exact=True).click();page.get_by_label('Redação',exact=True).select_option('concise');page.get_by_role('button',name='Opções',exact=True).click()
        page.get_by_label('Sua mensagem',exact=True).fill('Prepare uma estrutura de comunicação institucional para orientar a revisão de documentos, com destinatário e prazo pendentes.')
        page.get_by_role('button',name='Enviar solicitação',exact=True).click()
        expect(page.get_by_role('button',name='Abrir no editor',exact=True)).to_be_visible(timeout=150000)
        page.get_by_role('button',name='Abrir no editor',exact=True).click()
        page.get_by_label('Rascunho editável',exact=True).fill('Roteiro revisado: indicar destinatário pendente; explicar o fluxo de revisão; manter prazo e responsável como campos pendentes.')
        page.get_by_role('button',name='Usar roteiro na minuta →',exact=True).click()
        expect(page.locator('.context-chip').filter(has_text='Roteiro revisado')).to_be_visible()
        expect(page.get_by_role('button',name='Minuta',exact=True)).to_have_attribute('aria-pressed','true')
        page.get_by_role('button',name='Enviar solicitação',exact=True).click()
        expect(page.get_by_role('button',name='Abrir no editor',exact=True)).to_be_visible(timeout=150000)
        assert 'ROTEIRO REVISADO PELO USUÁRIO' in page.locator('.user-message').last.inner_text()
        checks['reviewed_plan_precedes_draft_generation']=True
        page.get_by_role('button',name='Novo trabalho',exact=True).click()
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(400)
        checks['mobile_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.locator('.work-main').screenshot(path='/artifacts/workbench-mobile.png')
        page.get_by_role('button',name='Mostrar histórico',exact=True).click()
        expect(page.get_by_label('Buscar no histórico',exact=True)).to_be_visible();checks['mobile_history_available']=True
        page.get_by_role('button',name='Mostrar histórico',exact=True).click()
        page.get_by_role('button',name='Preferências de acessibilidade',exact=True).click()
        dialog=page.get_by_role('dialog');dialog.get_by_label('Tamanho do texto').select_option(label='130%');dialog.get_by_label('Alto contraste',exact=True).check()
        page.keyboard.press('Escape');checks['reading_preferences_preserved']=page.evaluate("document.documentElement.classList.contains('a11y-high-contrast')")
        checks['large_text_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        checks['no_javascript_errors']=not errors
    finally:
        try:
            result=page.evaluate("""async ({chats,resources})=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();let ok=true;
            for(const id of chats){const r=await fetch('/moara/api/v1/chats/'+id+'/archive',{method:'POST',headers:{'X-Moara-CSRF':me.csrf_token}});ok=ok&&r.ok;}
            for(const id of resources){const r0=await fetch('/moara/api/v1/platform/resources/'+id);if(!r0.ok){ok=false;continue;}const row=await r0.json();const r=await fetch('/moara/api/v1/platform/resources/'+id+'/archive',{method:'POST',headers:{'Content-Type':'application/json','X-Moara-CSRF':me.csrf_token},body:JSON.stringify({version:row.version})});ok=ok&&r.ok;}return ok;}""",{'chats':chats,'resources':resources})
            checks['synthetic_content_archived']=result
        finally:checkpoint(context);context.close();browser.close()
report=json.loads(output.read_text());report['javascript_errors']=errors;report['candidate_proxy']=bool(fixture.get('candidate'));output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'checks':checks,'errors':errors},ensure_ascii=True),flush=True)
assert all(checks.values())
