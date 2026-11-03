import asyncio,json,sys,time
from pathlib import Path
from playwright.async_api import async_playwright
data=json.load(sys.stdin)
BASE='https://moara.am.trf1.gov.br'
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=['--no-sandbox','--ignore-certificate-errors-spki-list='+data['spki']])
  ctx=await browser.new_context(viewport={'width':1360,'height':960})
  await ctx.add_init_script('localStorage.setItem("token",'+json.dumps(data['token'])+');')
  page=await ctx.new_page()
  files=[];chats=[];report={'production':True,'synthetic_only':True};states=set()
  async def api(path,method='GET'):
   return await page.evaluate("""async ({path,method}) => {const r=await fetch(path,{method,headers:{Authorization:'Bearer '+localStorage.getItem('token')}});if(!r.ok)throw Error('Test API status '+r.status);return await r.json()}""",{'path':path,'method':method})
  async def response(r):
   if r.request.method!='POST':return
   try:
    if '/api/v1/files/?' in r.url and r.ok:
     d=await r.json()
     if d.get('filename')=='moara-teste-interface-ficticio.txt':files.append(d['id'])
    elif r.url.endswith('/api/v1/chats/new') and r.ok:
     d=await r.json()
     if d.get('id'):chats.append(d['id'])
   except Exception:pass
  page.on('response',response)
  try:
   await page.goto(BASE+'/',wait_until='domcontentloaded')
   await page.locator('#message-input-container').wait_for(timeout=60000)
   assert await page.locator('.chat-assistant').count()==0,'Expected a new empty conversation'
   report['feedback_loaded']=await page.evaluate('!!window.__moaraFeedback')
   text='DOCUMENTO INTEGRALMENTE FICTICIO PARA TESTE.\nProcedimento Alfa: o prazo e de cinco dias uteis.\n'
   text+='Informacao ficticia de preenchimento sem efeito juridico.\n'*1800
   await page.locator('input[type=file]').first.set_input_files({'name':'moara-teste-interface-ficticio.txt','mimeType':'text/plain','buffer':text.encode()})
   await page.get_by_text('moara-teste-interface-ficticio.txt',exact=True).first.wait_for()
   await page.locator('#message-input-container').screenshot(path='/tmp/moara-upload-real.png')
   await page.get_by_text('Pronto para consulta — 100%',exact=True).wait_for(timeout=600000)
   report['upload_completed']=True
   await page.locator('#chat-input').fill('Leia o início do arquivo fictício anexado com view_file e informe o prazo do procedimento Alfa. Responda em uma frase.')
   await page.locator('#chat-input').press('Enter')
   await page.get_by_text('Moara está preparando a resposta…',exact=True).wait_for(timeout=30000)
   await page.locator('#message-input-container').screenshot(path='/tmp/moara-resposta-real.png')
   report['preparing_visible']=True
   started=time.monotonic()
   while time.monotonic()-started<600:
    labels=await page.locator('#moara-feedback [role=status]').all_text_contents();states.update(labels)
    assistants=page.locator('.chat-assistant')
    if await assistants.count():
     answer=await assistants.last.inner_text()
     if 'estimated_context_budget_exceeded' in answer:raise RuntimeError('context_budget_exceeded')
     stops=await page.locator('#message-input-container button[aria-label="Stop"], #message-input-container button[aria-label="Parar"]').count()
     if len(answer)>10 and stops==0 and time.monotonic()-started>4:
      report['answer_mentions_five_days']=('cinco' in answer.lower() or '5' in answer) and 'dia' in answer.lower()
      report['answer_characters']=len(answer);break
    await asyncio.sleep(1)
   report['generation_states']=sorted(x for x in states if x.startswith('Moara '))
   report['context_error_seen']=any('ultrapassaram' in x for x in states)
   report['passed']=report.get('answer_mentions_five_days',False) and not report['context_error_seen']
   report['synthetic_answer']=answer[:1000]
   print(json.dumps(report,ensure_ascii=False),flush=True)
   assert report['passed'],'Synthetic document answer did not pass'
  finally:
   path=page.url.split('/c/')[-1] if '/c/' in page.url else ''
   if path and path not in chats:chats.append(path)
   for identifier in chats:
    await api('/api/v1/chats/'+identifier,'DELETE')
   for identifier in files:
    f=await api('/api/v1/files/'+identifier)
    assert f['filename']=='moara-teste-interface-ficticio.txt'
    await api('/api/v1/files/'+identifier,'DELETE')
   print(json.dumps({'synthetic_chats_removed':len(chats),'synthetic_files_removed':len(files)}),flush=True)
   await browser.close()
asyncio.run(main())
