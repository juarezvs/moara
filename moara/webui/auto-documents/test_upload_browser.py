import asyncio,json,sys
from pathlib import Path
from playwright.async_api import async_playwright
data=json.load(sys.stdin)
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=['--no-sandbox','--ignore-certificate-errors-spki-list='+data['spki']])
  ctx=await browser.new_context(viewport={'width':1360,'height':1000})
  await ctx.add_init_script('localStorage.setItem("token",'+json.dumps(data['token'])+');')
  page=await ctx.new_page();files=[];errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  filename='pdf-ficticio-176-paginas.pdf'
  async def api(path,method='GET'):
   return await page.evaluate("""async ({path,method})=>{const r=await fetch(path,{method,headers:{Authorization:'Bearer '+localStorage.getItem('token')}});if(!r.ok)throw Error('Test HTTP '+r.status);return r.json()}""",{'path':path,'method':method})
  async def response(r):
   if r.request.method=='POST' and '/api/v1/files/?' in r.url and r.ok:
    f=await r.json()
    if f.get('filename')==filename:files.append(f['id'])
  page.on('response',response)
  try:
   await page.goto('https://moara.am.trf1.gov.br/',wait_until='domcontentloaded')
   await page.locator('#chat-input').wait_for(timeout=60000)
   assert await page.locator('script[src*="feedback.js?v=20261027-upload-r5"]').count()==1
   await page.locator('input[type=file]').first.set_input_files('/tests/fixtures/'+filename)
   await page.get_by_text('Pronto para consulta — 100%',exact=True).wait_for(timeout=300000)
   await asyncio.sleep(1)
   assert len(files)==1,files
   f=await api('/api/v1/files/'+files[0]);assert f['data']['status']=='completed'
   assert 'FICTICIO' in f['data']['content']
   assert not errors,errors
   await page.locator('#message-input-container').screenshot(path='/tmp/upload-success.png')
   print(json.dumps({'passed':True,'bytes':11868084,'pages':176,'status':f['data']['status'],'extracted_characters':len(f['data']['content']),'javascript_errors':errors}),flush=True)
  finally:
   for identifier in files:
    f=await api('/api/v1/files/'+identifier);assert f['filename']==filename
    await api('/api/v1/files/'+identifier,'DELETE')
   print(json.dumps({'removed_synthetic_files':len(files)}),flush=True)
   await browser.close()
asyncio.run(main())
