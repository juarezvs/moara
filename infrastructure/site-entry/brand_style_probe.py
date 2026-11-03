import sys,json,hashlib
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline())
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--ignore-certificate-errors-spki-list='+fixture['spki']])
 c=b.new_context();c.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
 def proxy(route):
  u=urlsplit(route.request.url);r=route.fetch(url='http://'+fixture['candidate']+':8075'+u.path.removeprefix('/moara')+('?' +u.query if u.query else ''),max_redirects=0);route.fulfill(response=r)
 c.route('https://moara.am.trf1.gov.br/moara/**',proxy)
 page=c.new_page();page.goto('https://moara.am.trf1.gov.br/moara/chat',wait_until='domcontentloaded');expect(page.locator('.context-row')).to_have_count(5,timeout=45000)
 page.evaluate("()=>document.documentElement.classList.add('a11y-high-contrast')")
 values=page.evaluate("""()=>{const e=document.querySelector('.work-nav nav button:last-child'),s=document.querySelector('.history-search');return {contrast:document.documentElement.className,tabColor:getComputedStyle(e).color,svgColor:getComputedStyle(e.querySelector('svg')).color,searchDisplay:getComputedStyle(s).display,searchDirection:getComputedStyle(s).flexDirection,rules:[...document.styleSheets].flatMap(sheet=>{try{return [...sheet.cssRules].filter(r=>r.selectorText&&(r.selectorText.includes('history-search')||(r.selectorText.includes('high-contrast')&&r.selectorText.includes('work-nav')))).map(r=>r.cssText)}catch{return []}})}}""")
 session=next((v['value'] for v in c.cookies() if v['name']=='__Secure-moara_session'),None)
 Path('/artifacts/brand-style-probe.json').write_text(json.dumps({'values':values,'test_session_sha256':hashlib.sha256(session.encode()).hexdigest() if session else None}));print(json.dumps(values));c.close();b.close()
