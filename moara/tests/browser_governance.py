"""Real HTTPS governance UI and axe WCAG-tagged checks, synthetic resources only."""
import atexit,json,os,subprocess,sys,uuid
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
fixture=json.load(sys.stdin);out=Path('/tmp/moara-governance-qa');out.mkdir(exist_ok=True)
report={'checks':{},'page_errors':[],'failed_assets':[],'screenshots':[],'accessibility':{}}
def save():
    report['passed']=bool(report.get('completed')) and all(report['checks'].values()) and not report['page_errors'] and not report['failed_assets'] and all(not x for x in report['accessibility'].values())
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
atexit.register(save)
home=Path('/tmp/moara-browser-home');nss=home/'.pki/nssdb';nss.mkdir(parents=True,exist_ok=True)
ca=home/'moara-root.crt';ca.write_text(fixture['ca_pem'])
if not (nss/'cert9.db').exists():subprocess.run(['certutil','-N','--empty-password','-d','sql:'+str(nss)],check=True,capture_output=True)
subprocess.run(['certutil','-A','-d','sql:'+str(nss),'-n','Moara QA verified root','-t','C,,','-i',str(ca)],check=True,capture_output=True)
origin='https://localhost:8443'
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--host-resolver-rules=MAP localhost '+fixture['caddy_ip']],env={**os.environ,'HOME':str(home)})
    context=browser.new_context(viewport={'width':1672,'height':940},locale='pt-BR',reduced_motion='reduce')
    page=context.new_page()
    page.on('pageerror',lambda error:report['page_errors'].append(type(error).__name__+': '+str(error)[:180]))
    page.on('response',lambda r:report['failed_assets'].append({'status':r.status,'path':r.url.split('?')[0]}) if r.status>=400 and '/moara/' in r.url and '/api/' not in r.url else None)
    def audit(label):
        page.evaluate(fixture['axe_script'])
        value=page.evaluate("async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});return r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}));}")
        report['accessibility'][label]=value
    page.goto(origin+'/moara/login');page.locator('.login-card').wait_for();audit('login')
    page.locator('input[name=email]').fill(fixture['qa_login']['email']);page.locator('input[name=password]').fill(fixture['qa_login']['password'])
    page.locator('.login-card form button.primary').click();page.locator('.sidebar .profile strong').wait_for(timeout=30000)
    report['checks']['real_password_login_in_own_ui']=True
    report['checks']['ordinary_account_has_no_admin_navigation']=page.locator('.sidebar a[href="/moara/acessos"]').count()==0
    report['checks']['ordinary_account_admin_api_denied']=page.evaluate("async()=>(await fetch('/moara/api/v1/admin/accounts')).status")==403
    page.get_by_role('button',name='Sair da plataforma').click();page.locator('.login-card').wait_for()
    report['checks']['actual_logout_revokes_session']=page.evaluate("async()=>(await fetch('/moara/api/v1/auth/me')).status")==401
    context.add_init_script('localStorage.setItem("token",'+json.dumps(fixture['token'])+');')
    page.goto(origin+'/moara/');page.locator('.sidebar .profile strong').wait_for(timeout=30000)
    page.locator('moara-operations .operation-cards').wait_for();audit('dashboard-light')
    report['checks']['real_host_dashboard_visible']='—' not in page.locator('moara-operations .operation-cards').inner_text()
    page.screenshot(path=str(out/'dashboard-viewport.png'));report['screenshots'].append('dashboard-viewport.png')
    page.get_by_role('button',name='Ativar tema escuro').click();expect(page.locator('html')).to_have_attribute('data-theme','dark');audit('dashboard-dark')
    page.get_by_role('button',name='Ativar tema claro').click();expect(page.locator('html')).to_have_attribute('data-theme','light')
    page.goto(origin+'/moara/fontes');page.locator('moara-data-governance').wait_for();page.get_by_role('heading',name='Mapeamentos entre fontes').wait_for()
    group_name='_qa_ui_group_'+uuid.uuid4().hex[:8]
    page.get_by_role('button',name='Criar grupo',exact=True).click();page.locator('input[name=groupName]').fill(group_name)
    page.get_by_role('button',name='Salvar grupo',exact=True).click();row=page.locator('moara-data-governance tr').filter(has_text=group_name);expect(row).to_have_count(1)
    report['checks']['actual_group_created_in_ui']=True
    row.get_by_role('button',name='Excluir',exact=True).click();page.locator('input[name=confirmation]').fill(group_name)
    page.get_by_role('button',name='Confirmar exclusão',exact=True).click();expect(row).to_have_count(0);report['checks']['synthetic_ui_group_removed']=True
    mapping_name='_qa_ui_mapping_'+uuid.uuid4().hex[:8]
    page.get_by_role('button',name='Criar mapeamento',exact=True).click();page.locator('input[name=mappingName]').fill(mapping_name)
    page.locator('select[name=leftSource]').select_option(fixture['sources']['pg-ponto']);page.locator('select[name=rightSource]').select_option(fixture['sources']['mysql'])
    page.locator('select[name=leftField]').select_option('id');page.locator('select[name=rightField]').select_option('id')
    page.locator('textarea[name=compareFields]').fill('[{"left":"saldo_minutos","right":"saldo_minutos"}]')
    page.locator('textarea[name=criteria]').fill('Identificadores sintéticos iguais, saldos em minutos, somente amostras limitadas.')
    page.get_by_role('button',name='Salvar mapeamento aprovado').click();row=page.locator('moara-data-governance tr').filter(has_text=mapping_name);expect(row).to_have_count(1)
    report['checks']['actual_mapping_created_in_ui']=True
    row.get_by_role('button',name='Comparar',exact=True).click();page.get_by_role('button',name='Consultar e comparar').click()
    page.locator('moara-data-governance .answer-box h3').wait_for(timeout=90000)
    report['checks']['real_cross_database_ui']='2 correspondências' in page.locator('moara-data-governance .answer-box h3').inner_text()
    report['checks']['cross_limit_visible']='Consulta limitada' in page.locator('moara-data-governance .answer-box').inner_text()
    page.screenshot(path=str(out/'source-comparison.png'));report['screenshots'].append('source-comparison.png')
    row.get_by_role('button',name='Excluir',exact=True).click();page.locator('input[name=confirmation]').fill(mapping_name);page.get_by_role('button',name='Confirmar exclusão',exact=True).click()
    expect(row).to_have_count(0);report['checks']['synthetic_ui_mapping_removed']=True
    audit('sources')
    page.goto(origin+'/moara/modelos');page.get_by_role('heading',name='Modelos instalados').wait_for();audit('models')
    panel=page.locator('section.panel').filter(has=page.get_by_role('heading',name='Modelos instalados'))
    row=panel.locator('tr').filter(has_text='Gemma 4 12B').first;row.get_by_role('button',name='Remover',exact=True).click()
    report['checks']['model_removal_requires_name']=page.get_by_role('button',name='Confirmar remoção',exact=True).is_disabled()
    audit('removal-dialog');page.keyboard.press('Escape');expect(page.get_by_role('dialog')).to_have_count(0)
    page.get_by_role('button',name='Criar perfil',exact=True).click();expect(page.locator('input[name=newProfileId]')).to_be_visible();report['checks']['profile_creation_form_present']=True
    page.goto(origin+'/moara/acessos');page.get_by_role('heading',name='Chaves das integrações').wait_for();audit('access')
    page.get_by_role('button',name='Criar chave',exact=True).click();page.locator('input[name=keyData]').check();expect(page.locator('select[name=keySources]')).to_be_visible();report['checks']['integration_source_scopes_available']=True
    page.goto(origin+'/moara/identidade');page.get_by_role('heading',name='Identidade institucional',exact=True).wait_for();audit('identity')
    page.goto(origin+'/moara/chat');page.locator('#chat-draft').wait_for();audit('chat')
    page.goto(origin+'/moara/monitoramento/d/moara-operations/');page.get_by_text('Moara AI — Operações locais',exact=False).first.wait_for(timeout=60000)
    report['checks']['grafana_opens_in_verified_browser']=True
    page.screenshot(path=str(out/'monitoramento.png'));report['screenshots'].append('monitoramento.png')
    context.close();browser.close()
report['completed']=True
