import asyncio,json,sys,time,uuid
from pathlib import Path
from playwright.async_api import async_playwright
data=None;BASE='https://moara.am.trf1.gov.br'
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=['--no-sandbox','--ignore-certificate-errors-spki-list='+data['spki']])
  ctx=await browser.new_context(viewport={'width':1360,'height':1000})
  await ctx.add_init_script('localStorage.setItem("token",'+json.dumps(data['token'])+');')
  page=await ctx.new_page();file_ids=[];chat_id=None;events=[];uploads=0
  async def api(path,method='GET',body=None):
   return await page.evaluate("""async ({path,method,body}) => {const r=await fetch(path,{method,headers:{Authorization:'Bearer '+localStorage.getItem('token'),'Content-Type':'application/json'},...(body===null?{}:{body:JSON.stringify(body)})});if(!r.ok)throw Error('Test API status '+r.status);return r.json()}""",{'path':path,'method':method,'body':body})
  async def response(r):
   nonlocal uploads
   if r.request.method=='POST' and '/api/v1/files/?' in r.url and r.ok:
    f=await r.json()
    if f.get('filename')=='processo-ficticio-providencias.pdf':file_ids.append(f['id']);uploads+=1
  def socket(ws):
   def frame(payload):
    if not isinstance(payload,str) or not payload.startswith('42'):return
    try:
     event=json.loads(payload[payload.index('['):])[1];part=event.get('data') or {};detail=part.get('data') or {}
     if part.get('type')=='status' and isinstance(detail,dict):events.append(detail.get('action'))
    except Exception:pass
   ws.on('framereceived',frame)
  page.on('response',response);page.on('websocket',socket)
  async def no_background(route):
   body=route.request.post_data_json;body['background_tasks']={}
   await route.continue_(post_data=json.dumps(body))
  await page.route('**/api/chat/completions',no_background)
  try:
   await page.goto(BASE+'/',wait_until='domcontentloaded');await page.locator('#chat-input').wait_for(timeout=60000)
   await page.locator('input[type=file]').first.set_input_files('/tests/fixtures/processo-ficticio-providencias.pdf')
   await page.get_by_text('Pronto para consulta — 100%',exact=True).wait_for(timeout=180000)
   assert len(file_ids)==1
   fid=file_ids[0];name='processo-ficticio-providencias.pdf'
   attachment={'type':'file','id':fid,'name':name,'url':'/api/v1/files/'+fid,'collection_name':'file-'+fid,'status':'uploaded','file':{'id':fid,'filename':name,'meta':{'name':name,'content_type':'application/pdf'}}}
   messages=[];previous=None
   for i in range(8):
    for role in ['user','assistant']:
     mid=str(uuid.uuid4())
     content=('Sou da NUTEC. Analise este documento.' if i==0 else 'Continue o registro fictício '+str(i)+'.') if role=='user' else ('Registro histórico fictício, sem alterar as determinações do PDF. '*100)
     msg={'id':mid,'parentId':previous,'childrenIds':[],'role':role,'content':content,'timestamp':int(time.time()),'done':True}
     if role=='user':msg['models']=['auto']
     else:msg.update(model='auto',modelName='Moara AI - Automático',modelIdx=0)
     if i==0 and role=='user':msg['files']=[attachment]
     if messages:messages[-1]['childrenIds']=[mid]
     messages.append(msg);previous=mid
   seeded={x['id']:x for x in messages}
   created=await api('/api/v1/chats/new','POST',{'chat':{'title':'Teste fictício de continuidade com anexo','models':['auto'],'params':{},'messages':messages,'history':{'messages':seeded,'currentId':previous},'files':[attachment],'timestamp':int(time.time()*1000)}})
   chat_id=created['id']
   await page.goto(BASE+'/c/'+chat_id,wait_until='domcontentloaded');await page.locator('#chat-input').wait_for(timeout=60000)
   reports=[]
   for index,prompt in enumerate(['Qual a providência da NUTEC e o prazo desse mesmo documento?','O prazo de 12/11/2026 também vale para o encaminhamento do ofício pela SECAD?']):
    start_events=len(events)
    await page.locator('#chat-input').fill(prompt);await page.locator('#chat-input').press('Enter')
    start=time.monotonic();answer=''
    await asyncio.sleep(3)
    while time.monotonic()-start<360:
     answer=await page.locator('.chat-assistant').last.inner_text()
     stops=await page.locator('#message-input-container button[aria-label="Stop"],#message-input-container button[aria-label="Parar"]').count()
     if not stops and len(answer)>30 and 'Registro histórico fictício' not in answer:break
     await asyncio.sleep(1)
    lower=answer.lower()
    assert 'histórico está muito extenso' not in lower and 'estimated_context_budget_exceeded' not in lower
    compacted='moara_compacting_history' in events[start_events:]
    read='moara_reading_documents' in events[start_events:]
    passed=compacted and read and ('atlas' in lower and '12/11/2026' in lower if index==0 else 'secad' in lower and ('não' in lower or 'sem prazo' in lower))
    saved=(await api('/api/v1/chats/'+chat_id))['chat']['history']['messages']
    assert all(saved[mid]['content']==item['content'] for mid,item in seeded.items()),'Saved history changed'
    assert uploads==1,'Unexpected second upload'
    report={'turn':index+1,'history_compacted':compacted,'document_read_again':read,'saved_original_messages':len(seeded),'original_history_unchanged':True,'total_uploads':uploads,'answer':answer,'passed':passed}
    reports.append(report);print(json.dumps(report,ensure_ascii=False),flush=True)
    await page.locator('.chat-assistant').last.screenshot(path='/tmp/history-continuation-'+str(index)+'.png')
   assert all(x['passed'] for x in reports)
  finally:
   if chat_id:await api('/api/v1/chats/'+chat_id,'DELETE')
   for fid in file_ids:
    f=await api('/api/v1/files/'+fid);assert f['filename']=='processo-ficticio-providencias.pdf'
    await api('/api/v1/files/'+fid,'DELETE')
   print(json.dumps({'synthetic_chat_removed':bool(chat_id),'synthetic_files_removed':len(file_ids)}),flush=True)
   await browser.close()
if __name__=='__main__':
 data=json.load(sys.stdin)
 asyncio.run(main())
