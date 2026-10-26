"""Real LAN HTTPS and SJAM LDAP login. Bootstrap credential is stdin-only."""
import atexit
import json
import os
import subprocess
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

fixture=json.load(sys.stdin);out=Path('/tmp/moara-corporate-qa');out.mkdir(exist_ok=True)
report={'checks':{},'page_errors':[],'scope':'Real corporate DNS/LAN HTTPS, actual SJAM LDAPS, native chat and administrative registry'}
def save():
    report['passed']=bool(report.get('completed')) and all(report['checks'].values()) and not report['page_errors']
    (out/'report.json').write_text(json.dumps(report,indent=2))
atexit.register(save)
home=Path('/tmp/moara-browser-home');nss=home/'.pki/nssdb';nss.mkdir(parents=True,exist_ok=True)
ca=home/'root.crt';ca.write_text(fixture['ca_pem'])
if not (nss/'cert9.db').exists():subprocess.run(['certutil','-N','--empty-password','-d','sql:'+str(nss)],check=True,capture_output=True)
subprocess.run(['certutil','-A','-d','sql:'+str(nss),'-n','Moara corporate root','-t','C,,','-i',str(ca)],check=True,capture_output=True)
origin='https://moara.am.trf1.gov.br'
with sync_playwright() as p:
    browser=p.chromium.launch(chromium_sandbox=True,env={**os.environ,'HOME':str(home)})
    context=browser.new_context(locale='pt-BR',viewport={'width':1440,'height':1000},reduced_motion='reduce')
    page=context.new_page();page.on('pageerror',lambda e:report['page_errors'].append(str(e)[:120]));chat_id=None
    try:
        response=page.goto(origin+'/auth',wait_until='domcontentloaded')
        selector=page.locator('#moara-directory-choice');selector.wait_for(timeout=45000)
        report['checks']['lan_https_certificate_verified']=bool(response.security_details())
        report['checks']['seven_units_available']=selector.locator('option').count()==7
        selector.select_option('sjam');page.screenshot(path=str(out/'login.png'))
        page.locator('#username').fill(fixture['username']);page.locator('#password').fill(fixture['password'])
        with page.expect_response(lambda r:r.url.endswith('/api/v1/auths/ldap'),timeout=45000) as login:
            page.locator('form button[type=submit]').click()
        result=login.value
        report['checks']['unit_controls_submitted_identity']=result.request.post_data_json['user']=='sjam\\'+fixture['username']
        report['checks']['actual_sjam_network_login']=result.status==200 and bool(result.json().get('token'))
        if not report['checks']['actual_sjam_network_login']:raise AssertionError('sjam_login_failed')
        page.locator('#chat-input').wait_for(timeout=60000)
        models=page.evaluate("async()=>{const r=await fetch('/moara/v1/models',{headers:{Authorization:'Bearer '+localStorage.getItem('token')}});return {status:r.status,value:await r.json()}}")
        report['checks']['domain_origin_gateway_authorization']=models['status']==200 and any(m['id']=='auto' for m in models['value']['data'])
        page.locator('#model-selector-model-button').first.click();page.get_by_text('Moara AI · Automático',exact=True).first.click()
        page.locator('#chat-input').fill('Quem é você?');page.locator('#send-message-button').click()
        page.wait_for_url('**/c/**',timeout=30000);chat_id=page.url.rsplit('/',1)[-1]
        page.locator('#chat-container').get_by_text('Moara',exact=False).last.wait_for(timeout=60000)
        report['checks']['network_user_native_chat_answer']=True
        page.screenshot(path=str(out/'chat.png'))
        page.reload(wait_until='domcontentloaded');page.locator('#chat-input').wait_for(timeout=30000)
        report['checks']['native_chat_history_persists']=page.url.endswith(chat_id)
        admin=browser.new_context(locale='pt-BR',viewport={'width':1440,'height':1000})
        admin.add_init_script('localStorage.setItem("token",'+json.dumps(fixture['admin_token'])+');')
        admin_page=admin.new_page();admin_page.goto(origin+'/static/moara/directories.html',wait_until='domcontentloaded')
        expect(admin_page.locator('#admin')).to_be_visible(timeout=30000)
        orgs=admin_page.locator('#organizations');report['checks']['fifteen_organizations_imported']=orgs.locator('option').count()==16
        orgs.select_option('SJAM');expect(admin_page.locator('#organization [name=enabled]')).to_be_checked()
        admin_page.locator('#existing').select_option('sjam')
        expect(admin_page.locator('#directory [name=host]')).to_have_value('srvdc1-am.am.trf1.gov.br')
        report['checks']['sjam_directory_bound_to_correct_dc']=admin_page.locator('#directory [name=organization]').input_value()=='SJAM'
        report['checks']['privileged_ad_password_not_stored']=admin_page.locator('#directory [name=bind_password]').input_value()==''
        report['checks']['oracle_connector_linked_to_unit']=admin_page.locator('#organization-sources a').count()==1
        admin_page.screenshot(path=str(out/'organizations-desktop.png'),full_page=True)
        admin_page.set_viewport_size({'width':390,'height':844})
        report['checks']['registry_mobile_no_overflow']=admin_page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        admin_page.screenshot(path=str(out/'organizations-mobile.png'),full_page=True)
        admin.close();report['completed']=True
    finally:
        if chat_id:
            status=page.evaluate("async id=>(await fetch('/api/v1/chats/'+encodeURIComponent(id),{method:'DELETE',headers:{Authorization:'Bearer '+localStorage.getItem('token')}})).status",chat_id)
            report['checks']['synthetic_chat_removed']=status==200
        context.close();browser.close()
