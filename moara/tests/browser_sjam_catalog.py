"""Read-only UI acceptance: existing registrations and declared composite keys."""
import json,os,subprocess,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
fixture=json.load(sys.stdin);out=Path('/tmp/sjam-catalog-qa');out.mkdir()
home=Path('/tmp/sjam-browser-home');nss=home/'.pki/nssdb';nss.mkdir(parents=True)
ca=home/'root.crt';ca.write_text(fixture['ca_pem'])
subprocess.run(['certutil','-N','--empty-password','-d','sql:'+str(nss)],check=True,capture_output=True)
subprocess.run(['certutil','-A','-d','sql:'+str(nss),'-n','Moara test root','-t','C,,','-i',str(ca)],check=True,capture_output=True)
report={'checks':{},'page_errors':[]}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,chromium_sandbox=True,env={**os.environ,'HOME':str(home)})
    context=browser.new_context(viewport={'width':1440,'height':1000},locale='pt-BR',timezone_id='America/Manaus')
    context.add_init_script('localStorage.setItem("token",'+json.dumps(fixture['token'])+');')
    page=context.new_page();page.set_default_timeout(45000)
    page.on('pageerror',lambda error:report['page_errors'].append(str(error)[:160]))
    try:
        response=page.goto('https://moara.am.trf1.gov.br/moara/fontes?seccional=SJAM',wait_until='domcontentloaded')
        page.get_by_role('heading',name='Central de conectores').wait_for()
        expect(page.locator('[name=sourceSearch]')).to_have_value('SJAM')
        rows=page.locator('#source-registry tbody tr');expect(rows).to_have_count(2)
        report['checks']['verified_https']=bool(response.security_details())
        report['checks']['both_existing_registrations_listed']=all(name in ' '.join(rows.all_inner_texts()) for name in ('SJAM - Oracle SARH','SECP - SJAM'))
        rows.filter(has_text='SJAM - Oracle SARH').get_by_role('button',name='Detalhes',exact=True).click()
        page.get_by_role('button',name='Catálogo e acesso da IA',exact=True).click()
        catalog=page.locator('moara-source-catalog');expect(catalog.get_by_role('heading',name='Relacionamentos entre tabelas')).to_be_visible()
        expect(catalog.locator('table').first.locator('tbody tr')).to_have_count(275)
        report['checks']['all_oracle_objects_visible']=True
        catalog.locator('[name=catalogSearch]').fill('RH_AFASTAMENTOS_DIVERSOS')
        links=catalog.locator('table').nth(1).inner_text()
        report['checks']['composite_key_visible']=all(value in links for value in ('AFAD_FUNC_COD_FUNCIONARIO','AFAD_FUNC_SIGLA_FUNCIONARIO','FUNC_COD_FUNCIONARIO','FUNC_SESB_SIGLA_SECAO_SUBSECAO'))
        report['checks']['catalog_discovery_did_not_approve_absence_table']=not catalog.locator('table').first.get_by_role('checkbox').first.is_checked()
        catalog.locator('table').nth(1).scroll_into_view_if_needed()
        page.screenshot(path=str(out/'oracle-relationships-desktop.png'))
        page.set_viewport_size({'width':390,'height':844})
        catalog.locator('table').nth(1).scroll_into_view_if_needed()
        report['checks']['mobile_no_page_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(out/'oracle-relationships-mobile.png'))
        report['checks']['no_displayed_error']=page.locator('.error-box').count()==0
    finally:
        report['passed']=bool(report['checks']) and all(report['checks'].values()) and not report['page_errors']
        (out/'report.json').write_text(json.dumps(report,indent=2));context.close();browser.close()
if not report['passed']:raise SystemExit(1)
