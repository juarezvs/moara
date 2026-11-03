import sys,json
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline());checks={};errors=[];failures=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']])
    context=browser.new_context(viewport={'width':1280,'height':1000})
    def proxy(route):
        parsed=urlsplit(route.request.url)
        response=route.fetch(url='http://'+fixture['candidate']+':8075'+parsed.path.removeprefix('/moara'),timeout=30000)
        route.fulfill(response=response)
    context.route('https://moara.am.trf1.gov.br/moara/**',proxy)
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:200]))
    page.on('requestfailed',lambda r:failures.append({'url':r.url.split('?')[0],'failure':r.failure}))
    page.on('console',lambda m:print('BROWSER',m.type,m.text[:500],flush=True) if m.type=='error' else None)
    page.goto('https://moara.am.trf1.gov.br/moara/sobre',wait_until='networkidle')
    page.get_by_role('button',name='Ativar VLibras para o manifesto público',exact=True).click()
    page.wait_for_timeout(5000)
    print('FRAMES',[(f.url,f.locator('body').inner_text()[:80] if f.locator('body').count() else '') for f in page.frames],flush=True)
    frame=page.frame_locator('iframe.public-libras-frame')
    expect(frame.locator('#vlibras-button')).to_be_attached(timeout=45000)
    child=next(f for f in page.frames if '/accessibility/libras' in f.url)
    checks['libras_parent_isolated']=child.evaluate("(()=>{try{parent.document.body;return false}catch{return true}})()")
    checks['libras_cookie_isolated']=child.evaluate("(()=>{try{return document.cookie===''}catch{return true}})()")
    checks['public_libras_button_loaded']=True
    frame.locator('#vlibras-button').click()
    expect(frame.locator('#vlibras-app-root')).to_be_attached(timeout=45000)
    checks['libras_application_loaded']=True
    page.screenshot(path='/artifacts/moara2-libras.png')
    checks['no_javascript_errors']=not errors
    browser.close()
Path('/artifacts/moara2-libras.json').write_text(json.dumps({'checks':checks,'errors':errors,'failures':failures},ensure_ascii=False,indent=2))
print(json.dumps({'checks':checks,'errors':errors,'failures':failures},ensure_ascii=True))
assert all(checks.values())
