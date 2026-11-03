import json,re
from playwright.sync_api import sync_playwright,expect
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage'])
 context=browser.new_context(viewport={'width':1000,'height':800})
 page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)[:300]))
 page.route(re.compile('https?://'),lambda route:route.abort())
 page.goto('file:///tests/index.html',wait_until='load')
 cells=page.locator('button[data-cell]');expect(cells).to_have_count(9)
 for index in [0,3,1,4,2]:page.locator('[data-cell="'+str(index)+'"]').click()
 expect(page.locator('#status')).to_contain_text('X')
 expect(page.locator('#status')).to_contain_text(re.compile('venceu|ganhou|vencedor',re.I))
 last=page.locator('[data-cell="8"]')
 if last.is_enabled():last.click();expect(last).to_have_text('')
 page.locator('#reset').click()
 for index in range(9):expect(page.locator('[data-cell="'+str(index)+'"]')).to_have_text('')
 page.set_viewport_size({'width':390,'height':844})
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 assert not errors,errors
 print(json.dumps({'nine_playable_cells':True,'x_wins':True,'finished_game_does_not_continue':True,'reset_operates':True,'mobile_fits':True,'no_javascript_errors':True}))
 context.close();browser.close()
