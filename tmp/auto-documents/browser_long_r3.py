import asyncio,json,sys,time,re
from pathlib import Path
from playwright.async_api import async_playwright
data=json.load(sys.stdin);BASE='https://moara.am.trf1.gov.br'
CASES=[
 ('processo-ficticio-extenso.pdf',['boreal','20/12/2026'])]
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=['--no-sandbox','--ignore-certificate-errors-spki-list='+data['spki']])
  ctx=await browser.new_context(viewport={'width':1360,'height':1000})
  await ctx.add_init_script('localStorage.setItem("token",'+json.dumps(data['token'])+');')
  reports=[]
  for index,(filename,expected) in enumerate(CASES):
   page=await ctx.new_page();files=[];chats=set();read_events=[];sources=[]
   async def api(path,method='GET'):
    return await page.evaluate("""async ({path,method}) => {const r=await fetch(path,{method,headers:{Authorization:'Bearer '+localStorage.getItem('token')}});if(!r.ok)throw Error('Test API status '+r.status);return r.json()}""",{'path':path,'method':method})
   async def response(r):
    if r.request.method=='POST' and '/api/v1/files/?' in r.url and r.ok:
     f=await r.json()
     if f.get('filename')==filename:files.append(f['id'])
   def socket(ws):
    def frame(payload):
     if not isinstance(payload,str) or not payload.startswith('42'):return
     try:
      event=json.loads(payload[payload.index('['):])[1]
      if not isinstance(event,dict):return
      packet=event.get('data') or {};detail=packet.get('data') or {}
      if packet.get('type')=='status' and isinstance(detail,dict) and detail.get('action')=='moara_reading_documents':read_events.append(detail.get('done'))
      if isinstance(detail,dict) and detail.get('sources'):sources.extend(detail['sources'])
     except Exception:pass
    ws.on('framereceived',frame)
   page.on('response',response);page.on('websocket',socket)
   async def no_background(route):
    body=route.request.post_data_json;body['background_tasks']={}
    await route.continue_(post_data=json.dumps(body))
   await page.route('**/api/chat/completions',no_background)
   try:
    await page.goto(BASE+'/',wait_until='domcontentloaded');await page.locator('#chat-input').wait_for(timeout=60000)
    assert await page.locator('.chat-assistant').count()==0
    await page.locator('input[type=file]').first.set_input_files(str(Path('/tests/fixtures')/filename))
    await page.get_by_text('Pronto para consulta — 100%',exact=True).wait_for(timeout=240000)
    await asyncio.sleep(1)
    await page.locator('#chat-input').fill('Sou da NUTEC. Preciso fazer algo relacionado a este processo? Informe a providência e o prazo, se houver.')
    await page.locator('#chat-input').press('Enter')
    started=time.monotonic();answer=''
    while time.monotonic()-started<360:
     if '/c/' in page.url:chats.add(page.url.split('/c/')[-1].split('?')[0])
     if await page.locator('.chat-assistant').count():
      answer=await page.locator('.chat-assistant').last.inner_text()
      stop=await page.locator('#message-input-container button[aria-label="Stop"],#message-input-container button[aria-label="Parar"]').count()
      if len(answer)>20 and not stop and time.monotonic()-started>3:break
     await asyncio.sleep(1)
    await page.locator('.chat-assistant').last.screenshot(path='/tmp/automatic-document-'+str(index)+'.png')
    lowered=answer.lower()
    contradiction=index!=1 and bool(re.search(r'\bnão há (?:determinações|providências|obrigações|tarefas)',lowered))
    passed=not contradiction and len(sources)>0 and all(x in lowered for x in expected) and False in read_events and True in read_events and 'estimated_context_budget_exceeded' not in lowered
    if index==1:passed=passed and ('ciência' in lowered or 'não há' in lowered or 'nenhuma' in lowered)
    report={'contradictory_absence_claim':contradiction,'selected_sources_contain_expected':all(term in json.dumps(sources,ensure_ascii=False).lower() for term in expected),'fixture':filename,'question_has_no_tool_command':True,'automatic_read_events':read_events,'source_events':len(sources),'answer':answer,'elapsed_seconds':round(time.monotonic()-started,1),'passed':passed}
    reports.append(report);print(json.dumps(report,ensure_ascii=False),flush=True)
   finally:
    if '/c/' in page.url:chats.add(page.url.split('/c/')[-1].split('?')[0])
    for identifier in chats:await api('/api/v1/chats/'+identifier,'DELETE')
    for identifier in files:
     f=await api('/api/v1/files/'+identifier);assert f['filename']==filename
     await api('/api/v1/files/'+identifier,'DELETE')
    print(json.dumps({'removed_synthetic_chats':len(chats),'removed_synthetic_files':len(files)}),flush=True)
    await page.close()
  await browser.close()
  assert all(r['passed'] for r in reports),'One or more automatic-reading cases failed'
if __name__=='__main__':asyncio.run(main())
