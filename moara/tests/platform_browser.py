import json,sys,re,uuid
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
fixture=json.load(sys.stdin);out=Path('/tmp/platform-browser');out.mkdir(exist_ok=True)
checks={};errors=[];prompt_title='Prompt ficticio '+uuid.uuid4().hex[:8]
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 context=browser.new_context(ignore_https_errors=True,viewport={'width':1440,'height':1000})
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:200]))
 page.goto('https://localhost:8443/moara/login')
 page.get_by_label('E-mail',exact=True).fill('admin@staging.invalid')
 page.locator('input[name=password]').fill(fixture['password'])
 page.get_by_role('button',name='Entrar',exact=False).click()
 page.get_by_role('link',name='Espaço de trabalho',exact=True).click()
 expect(page.get_by_role('heading',name='Espaço de trabalho',exact=True)).to_be_visible()
 checks['workspace_navigation']=True
 page.get_by_role('button',name='Prompts',exact=True).click()
 page.get_by_label('Título',exact=True).fill(prompt_title)
 page.get_by_label('Texto (use {{campo}} para variáveis)',exact=True).fill('Responda com base nas fontes autorizadas.')
 page.get_by_role('button',name='Salvar versão',exact=True).click()
 expect(page.get_by_role('button',name=prompt_title,exact=True)).to_be_visible()
 checks['prompt_created_from_browser']=True
 page.get_by_role('button',name='Histórico de versões',exact=True).click()
 expect(page.locator('.platform-output')).to_contain_text('version')
 checks['version_history_visible']=True
 page.get_by_role('button',name='MOARA FLOW',exact=True).click()
 page.get_by_label('Título',exact=True).fill('Fluxo fictício de homologação')
 page.get_by_label('Descrição ou instruções',exact=True).fill('Notificação simulada.')
 page.get_by_label('Mensagem de teste',exact=True).fill('Etapa fictícia configurada pela interface.')
 page.get_by_role('button',name='Adicionar etapa',exact=True).click()
 expect(page.get_by_role('button',name='Remover etapa',exact=True)).to_have_count(1)
 checks['workflow_step_builder']=True
 page.get_by_role('combobox',name=re.compile('^Especialidade')).select_option('architect')
 expect(page.get_by_role('combobox',name=re.compile('^Especialidade'))).to_have_value('architect')
 checks['nine_agent_options']=page.get_by_role('combobox',name=re.compile('^Especialidade')).locator('option').count()==9
 page.get_by_role('button',name='Salvar versão',exact=True).click()
 expect(page.get_by_role('button',name='Executar teste',exact=True)).to_be_visible()
 page.get_by_role('button',name='Executar teste',exact=True).click()
 expect(page.locator('tbody')).to_contain_text('Fluxo',timeout=20000)
 checks['workflow_enqueued_from_browser']=True
 page.screenshot(path=str(out/'desktop.png'),full_page=True)
 page.set_viewport_size({'width':390,'height':844})
 page.screenshot(path=str(out/'mobile.png'),full_page=True)
 checks['mobile_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth <= innerWidth+2')
 checks['all_images_loaded']=page.evaluate('Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)')
 checks['no_runtime_errors']=not errors
 report={'checks':checks,'errors':errors,'passed':all(checks.values()),'synthetic_only':True,'tls_scope':'isolated fixture certificate; production TLS verified separately'}
 (out/'report.json').write_text(json.dumps(report));print(json.dumps(report));browser.close()
 if not report['passed']:raise SystemExit(1)
