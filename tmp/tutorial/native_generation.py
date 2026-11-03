import asyncio,json,sys,time
from playwright.async_api import async_playwright
data=json.load(sys.stdin);BASE='https://moara.am.trf1.gov.br'
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=['--no-sandbox','--ignore-certificate-errors-spki-list='+data['spki']])
  ctx=await browser.new_context()
  await ctx.add_init_script('localStorage.setItem("token",'+json.dumps(data['token'])+');')
  page=await ctx.new_page();chats=[];events=[];paths=[]
  async def response(r):
   if r.request.method=='POST' and r.url.endswith('/api/v1/chats/new') and r.ok:chats.append((await r.json())['id'])
  def socket(ws):
   paths.append(ws.url.split('?')[0])
   def frame(payload):
    if not isinstance(payload,str) or not payload.startswith('42'):return
    try:
     event=json.loads(payload[payload.index('['):])[1]
     if isinstance(event,dict):events.append({'event_keys':list(event),'type':event.get('data',{}).get('type'),'done':event.get('data',{}).get('data',{}).get('done') if isinstance(event.get('data',{}).get('data'),dict) else None})
    except Exception:pass
   ws.on('framereceived',frame)
  page.on('response',response);page.on('websocket',socket)
  async def no_background(route):
   body=route.request.post_data_json
   if isinstance(body,dict):body['background_tasks']={}
   await route.continue_(post_data=json.dumps(body))
  await page.route('**/api/chat/completions',no_background)
  try:
   await page.goto(BASE+'/',wait_until='domcontentloaded');await page.locator('#chat-input').wait_for(timeout=60000)
   assert await page.locator('.chat-assistant').count()==0
   await page.locator('#chat-input').fill('Quem é você?');await page.locator('#chat-input').press('Enter')
   await page.locator('.chat-assistant').first.wait_for(timeout=60000)
   for _ in range(90):
    content=await page.locator('.chat-assistant').last.inner_text()
    stops=await page.locator('#message-input-container button[aria-label="Stop"], #message-input-container button[aria-label="Parar"]').count()
    if len(content)>10 and stops==0:break
    await asyncio.sleep(1)
   await asyncio.sleep(1)
   active=await page.get_by_text('Moara está preparando a resposta…',exact=True).count()
   print(json.dumps({'generation_indicator_cleared':active==0,'websocket_paths':paths,'events':events[-12:]}),flush=True)
   assert active==0,'Generation feedback remained visible after completion'
  finally:
   for identifier in chats:
    await page.evaluate("""async id=>{let r=await fetch('/api/v1/chats/'+id,{method:'DELETE',headers:{Authorization:'Bearer '+localStorage.getItem('token')}});if(!r.ok)throw Error('cleanup failed')}""",identifier)
   print(json.dumps({'synthetic_chats_removed':len(chats)}),flush=True)
   await browser.close()
asyncio.run(main())
