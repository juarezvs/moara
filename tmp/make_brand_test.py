from pathlib import Path
s=Path('infrastructure/site-entry/progress_test.py').read_text(encoding='utf8')
s=s.replace('import sys,json,hashlib,time','import sys,json,hashlib,time,re')
s=s.replace('work-progress-ui.json','brand-ui.json').replace('work-progress-rail.png','brand-workspace.png').replace('work-progress-processing.png','brand-processing.png').replace('work-progress-mobile.png','brand-mobile.png')
needle="        page.get_by_role('tab',name='Documentos',exact=True).click()"
pre='''        page.get_by_role('tab',name='Início',exact=True).click()
        checks['original_background_loaded']=page.evaluate("async()=>{const r=await fetch('/moara/brand/chat-bg.png');return r.ok&&(await r.arrayBuffer()).byteLength>10000;}")
        checks['original_background_applied']='chat-bg.png' in page.locator('.legal-workbench').evaluate('(e)=>getComputedStyle(e).backgroundImage')
        expect(page.get_by_role('heading',name='Como posso ajudar você hoje?')).to_be_visible()
        checks['six_institutional_suggestions']=page.locator('.work-starters button').count()==6
        expect(page.locator('#chat-draft')).to_have_count(1)
        nav=page.get_by_role('navigation',name='Central Moara')
        checks['central_links_are_real_routes']=all((a.get_attribute('href') or '').startswith(('/moara/','/static/moara/')) for a in nav.get_by_role('link').all())
        page.locator('.legal-workbench').screenshot(path='/artifacts/brand-desktop.png',mask=[page.locator('.history-items'),page.locator('.work-dossiers'),page.locator('.work-user')],mask_color='#0b142b')
        page.evaluate("()=>document.documentElement.setAttribute('data-theme','dark')")
        checks['dark_theme_has_light_text']=page.locator('.welcome-question').evaluate("(e)=>getComputedStyle(e).color")=='rgb(237, 244, 255)'
        page.locator('.work-main').screenshot(path='/artifacts/brand-dark.png')
        page.evaluate("()=>document.documentElement.setAttribute('data-theme','light')")
        page.get_by_role('button',name='Analisar documentos Arquivos, trechos e referências rastreáveis',exact=True).click()
        expect(page.locator('.document-dropzone')).to_be_visible();checks['document_suggestion_opens_upload']=True
        page.get_by_role('button',name='Novo trabalho',exact=True).click()
        page.locator('.work-starters button').nth(1).click();expect(page.get_by_role('heading',name='Conferir uma norma',exact=True)).to_be_visible();checks['law_suggestion_opens_reference_form']=True
        page.get_by_role('button',name='Novo trabalho',exact=True).click()
        for index,assistant,mode,term in [(2,'administrativa','Minuta','termo de referência'),(3,'gabinete','Planejar','cronologia'),(4,'desenvolvedora','Planejar','solução'),(5,'dados','Planejar','dados institucionais')]:
            page.locator('.work-starters button').nth(index).click()
            expect(page.get_by_label('Sua mensagem',exact=True)).to_have_value(re.compile('.*'+re.escape(term)+'.*',re.S))
            expect(page.get_by_role('button',name=mode,exact=True)).to_have_attribute('aria-pressed','true')
            page.get_by_role('button',name='Configurar assistente e modelo',exact=True).click()
            expect(page.get_by_label('Assistente',exact=True)).to_have_value(assistant)
            page.get_by_role('button',name='Opções',exact=True).click()
            page.get_by_role('button',name='Novo trabalho',exact=True).click()
        checks['draft_plan_software_and_data_suggestions_configure_real_assistants']=True
'''
assert needle in s;s=s.replace(needle,pre+needle,1)
needle="        page.evaluate(\"()=>document.documentElement.classList.remove('a11y-large-text')\")"
s=s.replace(needle,needle+'''
        page.evaluate("()=>document.documentElement.classList.add('a11y-high-contrast')")
        checks['high_contrast_removes_background_image']=page.locator('.legal-workbench').evaluate('(e)=>getComputedStyle(e).backgroundImage')=='none'
        checks['high_contrast_rail_icons_are_legible']=page.get_by_role('tab').last.evaluate("(e)=>{const c=document.createElement('canvas').getContext('2d');c.fillStyle=getComputedStyle(e).color;c.fillRect(0,0,1,1);const rgb=Array.from(c.getImageData(0,0,1,1).data).slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});return (.2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2]+.05)/.05>=7;}")
        page.evaluate("()=>document.documentElement.classList.remove('a11y-high-contrast')")
''',1)
Path('infrastructure/site-entry/brand_test.py').write_text(s,encoding='utf8')
s=s.replace("        page.locator('.work-main').screenshot(path='/artifacts/brand-mobile.png')", "        page.evaluate('()=>window.scrollTo(0,0)')\n        checks['mobile_message_field_is_immediately_available']=page.get_by_label('Sua mensagem',exact=True).evaluate('(e)=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;}')\n        page.locator('.work-main').screenshot(path='/artifacts/brand-mobile.png')")
Path('infrastructure/site-entry/brand_test.py').write_text(s,encoding='utf8')
s=Path('infrastructure/site-entry/run_progress_browser.py').read_text(encoding='utf8').replace('moara-progress-browser-','moara-brand-browser-').replace("WORK/'progress_test.py'","WORK/'brand_test.py'").replace("WORK/'progress-output'","WORK/'brand-output'").replace('work-progress-core-name.txt','brand-core-name.txt').replace('work-progress-ui.json','brand-ui.json')
s=s.replace("['work-progress-rail.png','work-progress-processing.png','work-progress-mobile.png','brand-ui.json']","['brand-desktop.png','brand-dark.png','brand-workspace.png','brand-processing.png','brand-mobile.png','brand-ui.json']")
Path('infrastructure/site-entry/run_brand_browser.py').write_text(s,encoding='utf8')
