import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path('/tests')
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=['--no-sandbox'])
  page=await browser.new_page()
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  stages=iter([
   {'status':'pending','progress':{'stage':'indexing','percent':25,'completed_chunks':16,'total_chunks':64}},
   {'status':'pending','progress':{'stage':'waiting','percent':25}},
   {'status':'completed'}])
  async def route(r):
   url=r.request.url
   if '/process/status' in url:await r.fulfill(json=next(stages,{'status':'completed'}))
   elif '/api/v1/files/' in url:await r.fulfill(json={'id':'fixture'})
   elif '/api/chat/completions' in url:await r.fulfill(json={'task_id':'fixture'})
   else:await r.fulfill(content_type='text/html',body='<div id="message-input-container"></div><div id="message-fixture"></div>')
  await page.route('http://moara.test/**',route);await page.goto('http://moara.test/')
  await page.evaluate("() => {window.WebSocket = class extends EventTarget {constructor(){super()}}}")
  await page.add_style_tag(content=(ROOT/'feedback.css').read_text())
  await page.add_script_tag(content=(ROOT/'feedback.js').read_text())
  await page.evaluate("""async () => {const f=new FormData();f.append('file',new File(['ficticio'],'teste.txt')); const r=await fetch('/api/v1/files/',{method:'POST',body:f});if(!(await r.json()).id)throw Error('response changed');}""")
  await page.get_by_text('Indexando: 25% (16/64 trechos)').wait_for()
  assert await page.locator('progress').evaluate('(el) => el.value')==25
  await page.get_by_text('Aguardando capacidade para continuar a indexação…').wait_for()
  await page.get_by_text('Pronto para consulta — 100%').wait_for()
  await page.evaluate("fetch('/api/chat/completions',{method:'POST'})")
  await page.get_by_text('Moara está preparando a resposta…').wait_for()
  await page.evaluate("""() => {window.testSocket=new WebSocket('ws://moara.test/ws/socket.io');testSocket.dispatchEvent(new MessageEvent('message',{data:'42'+JSON.stringify(['chat-events',{message_id:'fixture',data:{type:'chat:completion',data:{choices:[{delta:{content:'resposta'}}]}}}])}));}""")
  await page.get_by_text('Moara está escrevendo a resposta…').wait_for()
  await page.evaluate("""testSocket.dispatchEvent(new MessageEvent('message',{data:'42'+JSON.stringify(['chat-events',{message_id:'fixture',data:{type:'chat:completion',data:{done:true}}}])}))""")
  assert await page.get_by_text('Resposta da Moara',exact=True).count()==0
  await page.evaluate("fetch('/api/chat/completions',{method:'POST'})")
  await page.evaluate("""testSocket.dispatchEvent(new MessageEvent('message',{data:'42'+JSON.stringify(['chat-events',{message_id:'fixture',data:{type:'chat:message:error',data:{error:'estimated_context_budget_exceeded'}}}])}))""")
  await page.get_by_text('O histórico e os trechos do arquivo',exact=False).wait_for()
  assert not errors,errors
  await browser.close()
  print(json.dumps({'browser_checks':'passed','measured_progress':True,'waiting':True,'completed':True,'generation_events':True,'portuguese_context_error':True,'console_errors':errors}))
asyncio.run(main())
