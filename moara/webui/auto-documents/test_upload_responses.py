import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=['--no-sandbox'])
  errors=[];results=[]
  cases=[(413,'',413),(502,'<html>bad gateway</html>',502),(200,'',502),(200,'{"id":',502),(200,'null',502),(200,'{}',502),(429,'',429),(400,'{"detail":"Arquivo não permitido."}',400),(200,'{"id":"fixture","data":{"status":"pending"}}',200)]
  for status,body,expected in cases:
   page=await browser.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
   async def route(r):
    if '/process/status' in r.request.url:await r.fulfill(json={'status':'completed'})
    elif '/api/v1/files/' in r.request.url:await r.fulfill(status=status,body=body)
    else:await r.fulfill(content_type='text/html',body='<div id="message-input-container"></div>')
   await page.route('http://moara.test/**',route);await page.goto('http://moara.test/')
   await page.add_script_tag(content=Path('/tests/feedback.js').read_text())
   result=await page.evaluate("""async()=>{const form=new FormData();form.append('file',new File(['teste'],'ficticio.pdf'));const r=await fetch('/api/v1/files/',{method:'POST',body:form});return {status:r.status,body:await r.json()}}""")
   assert result['status']==expected,result
   if expected!=200:
    assert isinstance(result['body'].get('detail'),str)
    assert 'JSON' not in result['body']['detail']
    assert await page.get_by_text('Pronto para consulta — 100%',exact=True).count()==0
   else:await page.get_by_text('Pronto para consulta — 100%',exact=True).wait_for()
   results.append({'input_status':status,'input_body_bytes':len(body),'result_status':expected})
   await page.close()
  assert not errors,errors
  await browser.close();print(json.dumps({'passed':True,'cases':results,'javascript_errors':errors}))
asyncio.run(main())
