"""Real TLS browser test of the native Moara chat through its new gateway."""
import atexit
import json
import os
import subprocess
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

fixture=json.load(sys.stdin);out=Path('/tmp/moara-native-qa');out.mkdir(exist_ok=True)
report={'checks':{},'page_errors':[],'failed_assets':[]}
def save():
    report['passed']=bool(report.get('completed')) and all(report['checks'].values()) and not report['page_errors']
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
atexit.register(save)
home=Path('/tmp/moara-browser-home');nss=home/'.pki/nssdb';nss.mkdir(parents=True,exist_ok=True)
ca=home/'moara-root.crt';ca.write_text(fixture['ca_pem'])
if not (nss/'cert9.db').exists():subprocess.run(['certutil','-N','--empty-password','-d','sql:'+str(nss)],check=True,capture_output=True)
subprocess.run(['certutil','-A','-d','sql:'+str(nss),'-n','Moara QA root','-t','C,,','-i',str(ca)],check=True,capture_output=True)
origin='https://localhost:8443'
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--host-resolver-rules=MAP localhost '+fixture['caddy_ip']],env={**os.environ,'HOME':str(home)})
    context=browser.new_context(viewport={'width':1672,'height':940},locale='pt-BR',reduced_motion='reduce')
    context.add_init_script('localStorage.setItem("token",'+json.dumps(fixture['token'])+');')
    page=context.new_page();page.on('pageerror',lambda e:report['page_errors'].append(str(e)[:160]))
    response=page.goto(origin+'/',wait_until='domcontentloaded');page.locator('#chat-input').wait_for(timeout=60000)
    report['checks']['native_chat_tls_verified']=bool(response.security_details())
    report['checks']['native_branding']='Moara' in page.title()
    report['checks']['control_center_links']=page.locator('#moara-control-center a').count()==5
    expect(page.locator('#moara-control-center a').first).to_be_in_viewport()
    report['checks']['control_center_visible_in_sidebar']=True
    data=page.evaluate('''async()=>{const r=await fetch('/api/models',{headers:{Authorization:'Bearer '+localStorage.getItem('token')}});return await r.json()}''')
    report['checks']['automatic_model_available']=any(m['id']=='auto' for m in data.get('data',[]))
    # Native selector supports persisted personal choices; explicitly select auto.
    page.locator('#model-selector-model-button').first.click()
    item=page.get_by_text('Moara AI · Automático',exact=True)
    item.first.wait_for(timeout=15000);item.first.click()
    page.locator('#chat-input').fill('Responda apenas OK. Não use ferramentas.')
    page.locator('#send-message-button').click()
    page.wait_for_url('**/c/**',timeout=30000)
    report['chat_id']=page.url.rsplit('/',1)[-1]
    page.locator('#chat-container').get_by_text('OK.',exact=True).first.wait_for(timeout=180000)
    report['checks']['native_streaming_answer_rendered']=True
    page.screenshot(path=str(out/'native-chat-desktop.png'))
    page.reload(wait_until='domcontentloaded');page.locator('#chat-input').wait_for(timeout=30000)
    page.locator('#chat-container').get_by_text('OK.',exact=True).first.wait_for(timeout=30000)
    report['checks']['native_history_survives_reload']=True
    page.goto(origin+'/static/moara/directories.html',wait_until='domcontentloaded')
    expect(page.locator('#admin')).to_be_visible(timeout=20000)
    page.locator('#existing').select_option('am')
    expect(page.locator('[name=host]')).to_have_value('am.trf1.gov.br')
    report['checks']['corporate_directory_draft']=page.locator('[name=search_base]').input_value()=='DC=am,DC=trf1,DC=gov,DC=br' and not page.locator('[name=enabled]').is_checked()
    report['checks']['directory_password_not_returned']=page.locator('[name=bind_password]').input_value()==''
    page.screenshot(path=str(out/'directories-desktop.png'))
    page.set_viewport_size({'width':390,'height':844})
    report['checks']['directories_mobile_no_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(out/'directories-mobile.png'),full_page=True)
    page.goto(origin+'/moara/acessos',wait_until='domcontentloaded');page.get_by_role('heading',name='Chaves das integrações').wait_for(timeout=30000)
    report['checks']['native_session_opens_core_api_keys']=True
    page.goto(origin+'/moara/fontes',wait_until='domcontentloaded');page.get_by_role('heading',name='Central de conectores').wait_for(timeout=30000)
    report['checks']['native_session_opens_data_sources']=True
    # Delete precisely the new synthetic chat, never titles or existing histories.
    result=page.evaluate('''async id=>{const r=await fetch('/api/v1/chats/'+encodeURIComponent(id),{method:'DELETE',headers:{Authorization:'Bearer '+localStorage.getItem('token')}});return r.status}''',report['chat_id'])
    report['checks']['synthetic_chat_removed']=result==200
    report['completed']=True;context.close();browser.close()
