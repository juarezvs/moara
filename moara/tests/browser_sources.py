"""Real UI wizard, SQLite read and SQL-assisted chat over verified HTTPS."""
import atexit
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
fixture=json.load(sys.stdin);out=Path('/tmp/moara-sources-qa');out.mkdir(exist_ok=True)
report={'checks':{},'page_errors':[],'failed_assets':[],'screenshots':[],'created_source_ids':[],'created_chat_ids':[]}
def save():
    report['passed']=bool(report.get('completed')) and all(report['checks'].values()) and not report['page_errors'] and not report['failed_assets']
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
atexit.register(save)
home=Path('/tmp/moara-browser-home');nss=home/'.pki/nssdb';nss.mkdir(parents=True,exist_ok=True)
ca=home/'moara-root.crt';ca.write_text(fixture['ca_pem'])
if not (nss/'cert9.db').exists():subprocess.run(['certutil','-N','--empty-password','-d','sql:'+str(nss)],check=True,capture_output=True)
subprocess.run(['certutil','-A','-d','sql:'+str(nss),'-n','Moara QA verified root','-t','C,,','-i',str(ca)],check=True,capture_output=True)
snapshot=out/'synthetic.sqlite';snapshot.unlink(missing_ok=True);db=sqlite3.connect(snapshot)
db.execute('CREATE TABLE inventory(id integer PRIMARY KEY,nome text,email text)')
db.executemany('INSERT INTO inventory VALUES(?,?,?)',[(1,'Synthetic Item Alpha','a@example.invalid'),(2,'Synthetic Item Beta','b@example.invalid'),(3,'Synthetic Item Gamma','c@example.invalid')]);db.commit();db.close()
name='_moara_browser_fixture_'+uuid.uuid4().hex[:8]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--host-resolver-rules=MAP localhost '+fixture['caddy_ip']],env={**os.environ,'HOME':str(home)})
    context=browser.new_context(viewport={'width':1672,'height':940},locale='pt-BR',timezone_id='America/Manaus',reduced_motion='reduce')
    context.add_init_script('localStorage.setItem("token",'+json.dumps(fixture['token'])+');')
    page=context.new_page();page.set_default_timeout(30000)
    page.on('pageerror',lambda error:report['page_errors'].append(type(error).__name__+': '+str(error)[:180]))
    def observe(response):
        path=response.url.split('?')[0]
        if response.status>=400 and '/moara/' in path and '/api/' not in path:report['failed_assets'].append({'path':path,'status':response.status})
        if response.request.method=='POST' and response.status in (200,201):
            if path.endswith('/moara/api/v1/connectors/sources'):report['created_source_ids'].append(response.json()['id'])
            if path.endswith('/moara/api/v1/chats'):report['created_chat_ids'].append(response.json()['id'])
    page.on('response',observe)
    response=page.goto('https://localhost:8443/moara/fontes',wait_until='domcontentloaded');page.get_by_role('heading',name='Central de conectores').wait_for()
    report['checks']['browser_tls_verified']=bool(response.security_details())
    expect(page.locator('.connector-card')).to_have_count(7)
    report['checks']['seven_live_connector_cards']=True
    page.get_by_role('button',name='Adicionar fonte').click()
    page.get_by_label('Nome da fonte',exact=True).fill(name);page.locator('select[name=kind]').select_option('sqlite')
    page.get_by_label('Descrição',exact=True).fill('Synthetic UI acceptance fixture. Only inventory id and nome are authorized. No corporate data.')
    page.get_by_role('button',name='Continuar').click();page.locator('input[type=file]').set_input_files(str(snapshot))
    page.get_by_text('Snapshot importado',exact=True).wait_for(timeout=30000)
    page.get_by_role('button',name='Continuar').click();page.get_by_role('button',name='Testar conexão',exact=True).click()
    page.get_by_text('Conexão aprovada para consultas somente de leitura.',exact=False).wait_for(timeout=45000)
    report['checks']['wizard_readonly_verification']=True
    page.get_by_role('button',name='Continuar').click();page.get_by_role('button',name='Descobrir catálogo').click()
    page.locator('.catalog-object').filter(has_text='main.inventory').get_by_role('checkbox').first.check()
    report['checks']['sensitive_field_not_selected']=not page.locator('.field-options').get_by_role('checkbox',name='email',exact=False).is_checked()
    page.get_by_role('button',name='Continuar').click();page.get_by_label('Limite de linhas por consulta').fill('2')
    page.get_by_role('button',name='Continuar').click();page.get_by_role('button',name='Salvar e ativar fonte').click()
    page.locator('.source-detail').get_by_role('heading',name=name,exact=True).wait_for(timeout=60000)
    report['checks']['six_step_wizard_activated_source']=True
    page.get_by_role('button',name='Consulta de leitura',exact=True).click();page.get_by_role('button',name='Executar consulta de leitura').click()
    page.locator('.query-result').wait_for(timeout=45000)
    report['checks']['bounded_query_rows']=page.locator('.query-result tbody tr').count()==2
    report['checks']['sensitive_field_excluded']='email' not in page.locator('.query-result thead').inner_text().lower()
    report['checks']['incomplete_result_visible']='Resultado limitado' in page.locator('.query-result').inner_text()
    report['checks']['query_no_error']=page.locator('.error-box').count()==0
    page.screenshot(path=str(out/'source-query-desktop.png'));report['screenshots'].append('source-query-desktop.png')
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(300)
    report['checks']['source_mobile_no_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(out/'source-query-mobile.png'));report['screenshots'].append('source-query-mobile.png')
    page.set_viewport_size({'width':1672,'height':940});page.goto('https://localhost:8443/moara/chat',wait_until='domcontentloaded')
    page.locator('select[name=profile]').select_option('coding');page.get_by_role('checkbox',name='Consultar fontes autorizadas',exact=False).check()
    question='Na fonte '+name+', liste id e nome dos registros. Use somente essa fonte, sem outras tabelas, e retorne no máximo duas linhas.'
    page.locator('#chat-draft').fill(question);page.get_by_role('button',name='Enviar').click()
    expect(page.locator('.message')).to_have_count(2,timeout=300000);page.locator('.stream-status').wait_for(state='hidden',timeout=300000)
    report['checks']['sql_tool_chat_answer']=name in page.locator('.message').last.inner_text()
    report['checks']['sql_tool_chat_citations']='Fontes consultadas' in page.locator('.message').last.inner_text()
    report['checks']['sql_tool_chat_no_error']=page.locator('.error-box').count()==0
    page.screenshot(path=str(out/'sql-chat-desktop.png'));report['screenshots'].append('sql-chat-desktop.png')
    page.get_by_role('button',name='Excluir conversa',exact=True).click();page.get_by_role('button',name='Confirmar exclusão',exact=True).click();expect(page.locator('.message')).to_have_count(0)
    report['checks']['synthetic_chat_removed']=True
    page.goto('https://localhost:8443/moara/fontes',wait_until='domcontentloaded')
    row=page.locator('tbody tr').filter(has_text=name);row.get_by_role('button',name='Detalhes').click()
    page.get_by_role('button',name='Desativar fonte').click();page.get_by_role('button',name='Revalidar e ativar').wait_for(timeout=30000)
    page.get_by_role('button',name='Excluir fonte',exact=True).click();page.get_by_label('Nome da fonte para confirmação').fill(name)
    page.get_by_role('button',name='Confirmar exclusão da fonte').click();page.locator('.source-detail').wait_for(state='hidden',timeout=30000)
    report['checks']['synthetic_source_removed']=True
    context.close();browser.close()
report['completed']=True
