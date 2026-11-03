import sys,json
from playwright.sync_api import sync_playwright
fixture=json.loads(sys.stdin.readline())
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']])
 context=browser.new_context(viewport={'width':1440,'height':1000})
 context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
 page=context.new_page();page.goto('https://moara.am.trf1.gov.br/',wait_until='domcontentloaded');page.wait_for_timeout(5000)
 print(json.dumps({'path':page.url.split('moara.am.trf1.gov.br')[-1],
  'inputs':page.locator('textarea,[contenteditable=true]').evaluate_all("els=>els.map(e=>({tag:e.tagName,id:e.id,role:e.getAttribute('role'),placeholder:e.getAttribute('placeholder')}))"),
  'send_buttons':page.locator('button[id*=send]').evaluate_all("els=>els.map(e=>({id:e.id,label:e.getAttribute('aria-label')}))"),
  'file_inputs':page.locator('input[type=file]').evaluate_all("els=>els.map(e=>({id:e.id,accept:e.getAttribute('accept')}))"),
  'dialogs':page.get_by_role('dialog').count()},ensure_ascii=True))
 context.close();browser.close()
