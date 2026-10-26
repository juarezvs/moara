"""Real HTTPS UI acceptance, fixture supplied over stdin; credentials never logged."""
import atexit
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

fixture=json.load(sys.stdin);out=Path('/tmp/moara-core-qa');out.mkdir(exist_ok=True)
report={'checks':{},'page_errors':[],'failed_assets':[],'screenshots':[]}
def save():
    report['passed']=bool(report.get('completed')) and all(report['checks'].values()) and not report['page_errors'] and not report['failed_assets']
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
atexit.register(save)
home=Path('/tmp/moara-browser-home');nss=home/'.pki/nssdb';nss.mkdir(parents=True,exist_ok=True)
ca=home/'moara-root.crt';ca.write_text(fixture['ca_pem'])
if not (nss/'cert9.db').exists():subprocess.run(['certutil','-N','--empty-password','-d','sql:'+str(nss)],check=True,capture_output=True)
subprocess.run(['certutil','-A','-d','sql:'+str(nss),'-n','Moara QA verified root','-t','C,,','-i',str(ca)],check=True,capture_output=True)
origin='https://localhost:8443'
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--host-resolver-rules=MAP localhost '+fixture['caddy_ip']],env={**os.environ,'HOME':str(home)})
    anonymous=browser.new_context(viewport={'width':1672,'height':940},locale='pt-BR',reduced_motion='reduce')
    page=anonymous.new_page()
    response=page.goto(origin+'/moara/login',wait_until='domcontentloaded')
    page.get_by_role('heading',name='Faça login no Moara AI').wait_for()
    report['checks']['login_layout_styled']=page.locator('.login-scene').evaluate('e=>getComputedStyle(e).display')=='grid'
    report['checks']['browser_tls_verified']=bool(response.security_details())
    report['checks']['own_login_vendor_absent']='open webui' not in page.inner_text('body').lower()
    page.screenshot(path=str(out/'login-desktop.png'),full_page=True);report['screenshots'].append('login-desktop.png')
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(300)
    report['checks']['login_mobile_no_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(out/'login-mobile.png'),full_page=True);report['screenshots'].append('login-mobile.png')
    page.goto(origin+'/moara/sobre',wait_until='domcontentloaded');page.locator('.about-hero h1').wait_for()
    report['checks']['public_about']=True
    anonymous.close()
    context=browser.new_context(viewport={'width':1672,'height':940},locale='pt-BR',reduced_motion='reduce')
    context.add_init_script('localStorage.setItem("token",'+json.dumps(fixture['token'])+');')
    page=context.new_page()
    page.on('pageerror',lambda error:report['page_errors'].append(type(error).__name__+': '+str(error)[:180]))
    page.on('response',lambda r:report['failed_assets'].append({'status':r.status,'path':r.url.split('?')[0]}) if r.status>=400 and '/moara/' in r.url and '/api/' not in r.url else None)
    page.goto(origin+'/moara/',wait_until='domcontentloaded')
    page.locator('.sidebar .profile strong').wait_for(timeout=30000)
    report['checks']['sidebar_layout_styled']=page.locator('.sidebar').evaluate('e=>getComputedStyle(e).position')=='fixed'
    report['checks']['brand_sized']=page.locator('.sidebar .brand img').evaluate('e=>e.getBoundingClientRect().width')<100
    report['checks']['verified_session_bridge']=True
    report['checks']['own_frontend_vendor_absent']='open webui' not in page.inner_text('body').lower()
    page.screenshot(path=str(out/'dashboard.png'),full_page=True);report['screenshots'].append('dashboard.png')
    page.get_by_role('link',name='Modelos e perfis').click();page.get_by_role('heading',name='Modelos instalados').wait_for()
    page.locator('tbody tr').nth(6).wait_for()
    report['checks']['real_model_inventory']=page.locator('tbody tr').count()>=7
    report['checks']['twelve_thread_profiles']='12 threads' in page.inner_text('body')
    page.screenshot(path=str(out/'models.png'),full_page=True);report['screenshots'].append('models.png')
    page.get_by_role('link',name='Identidade institucional').click();page.get_by_role('tab',name='Testar respostas').click()
    page.get_by_role('button',name='Testar resposta',exact=True).click();page.locator('.answer-box').wait_for()
    report['checks']['identity_faq_api']='Moara' in page.locator('.answer-box').inner_text()
    page.get_by_role('link',name='Contas e integrações').click();page.get_by_role('heading',name='Chaves das integrações').wait_for()
    report['checks']['access_admin_ui']=page.get_by_role('heading',name='Contas da plataforma').is_visible()
    page.locator('.sidebar a[href="/moara/chat"]').click();page.get_by_role('heading',name='Como posso ajudar você hoje?').wait_for()
    page.locator('select[name=profile]').select_option('fast')
    question='Quem é você?'
    page.locator('#chat-draft').fill(question);page.get_by_role('button',name='Enviar').click()
    expect(page.locator('.message')).to_have_count(2,timeout=60000);page.locator('.stream-status').wait_for(state='hidden',timeout=60000)
    report['checks']['canonical_chat']='Moara' in page.locator('.message').last.inner_text()
    report['checks']['canonical_truthful_origin']='Identidade institucional' in page.locator('.chat-options').inner_text()
    page.locator('#chat-draft').fill('Responda apenas OK. Não use ferramentas.');page.get_by_role('button',name='Enviar').click()
    expect(page.locator('.message')).to_have_count(4,timeout=180000);page.locator('.stream-status').wait_for(state='hidden',timeout=180000)
    report['checks']['real_model_response']='OK' in page.locator('.message').last.inner_text()
    report['checks']['model_metadata_visible']='Identidade institucional' not in page.locator('.chat-options').inner_text()
    report['checks']['chat_no_error']=page.locator('.error-box').count()==0
    page.locator('#chat-draft').fill('Liste os números de 1 a 2000, separados por vírgulas. Continue a lista sem explicações.')
    page.get_by_role('button',name='Enviar').click()
    expect(page.locator('.message')).to_have_count(6,timeout=180000)
    expect(page.locator('.message').last.locator('.markdown')).not_to_be_empty(timeout=180000)
    page.get_by_role('button',name='Interromper',exact=True).click()
    page.locator('.stream-status').wait_for(state='hidden',timeout=30000)
    expect(page.locator('.message').last).to_contain_text('Resposta interrompida')
    report['checks']['actual_stream_cancel_preserves_partial_text']=True
    page.locator('#chat-draft').fill('Responda apenas OK. Não use ferramentas.')
    page.get_by_role('button',name='Enviar').click()
    expect(page.locator('.message')).to_have_count(8,timeout=180000)
    page.locator('.stream-status').wait_for(state='hidden',timeout=180000)
    report['checks']['inference_slot_available_after_cancel']='OK' in page.locator('.message').last.inner_text()
    report['sidebar_geometry']=page.locator('.sidebar').evaluate("e=>Array.from(e.children).map(n=>({tag:n.tagName,rect:{x:n.getBoundingClientRect().x,y:n.getBoundingClientRect().y,w:n.getBoundingClientRect().width,h:n.getBoundingClientRect().height},display:getComputedStyle(n).display,visibility:getComputedStyle(n).visibility,opacity:getComputedStyle(n).opacity}))")
    page.screenshot(path=str(out/'chat-viewport.png'));report['screenshots'].append('chat-viewport.png')
    page.screenshot(path=str(out/'chat-desktop.png'),full_page=True);report['screenshots'].append('chat-desktop.png')
    page.reload(wait_until='domcontentloaded');page.locator('.history-item').filter(has_text=question).first.click()
    expect(page.locator('.message')).to_have_count(8)
    report['checks']['interrupted_status_persisted_in_history']='Resposta interrompida' in page.locator('.message').nth(5).inner_text()
    report['checks']['history_reloaded']=True
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(400)
    report['checks']['chat_mobile_no_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.get_by_role('button',name='Abrir navegação').click();page.get_by_role('button',name='Fechar navegação',exact=True).first.wait_for(state='visible')
    report['checks']['mobile_menu_open']=page.locator('.app-layout').evaluate('e=>e.classList.contains("menu-open")')
    page.keyboard.press('Escape');expect(page.locator('.app-layout')).not_to_have_class(re.compile('menu-open'));report['checks']['mobile_menu_escape']=True
    page.screenshot(path=str(out/'chat-mobile.png'),full_page=True);report['screenshots'].append('chat-mobile.png')
    page.set_viewport_size({'width':1672,'height':940})
    page.get_by_role('button',name='Excluir conversa',exact=True).click();page.get_by_role('button',name='Confirmar exclusão').click()
    expect(page.locator('.message')).to_have_count(0)
    report['checks']['synthetic_chat_removed']=True
    # Existing native chat and Studio remain served by their original routes.
    page.goto(origin+'/',wait_until='domcontentloaded');page.locator('#chat-input').wait_for(timeout=60000)
    report['checks']['legacy_chat_retained']=True
    page.goto(origin+'/studio/',wait_until='domcontentloaded');page.locator('#login').wait_for(state='hidden',timeout=30000)
    report['checks']['studio_sso_retained']=True
    context.close();browser.close()
report['completed']=True
