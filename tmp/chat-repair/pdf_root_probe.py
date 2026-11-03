import sys,json,time,base64
from pathlib import Path
from playwright.sync_api import sync_playwright
fixture=json.loads(sys.stdin.readline());report={}
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']])
 context=browser.new_context(viewport={'width':1440,'height':1000})
 context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
 page=context.new_page();page.goto('https://moara.am.trf1.gov.br/',wait_until='domcontentloaded');page.wait_for_selector('#chat-input',timeout=30000)
 if fixture.get('existing_file_id'):identifier=fixture['existing_file_id']
 else:
  data=base64.b64decode(fixture['pdf_base64'])
  with page.expect_response(lambda r:r.request.method=='POST' and '/api/v1/files/' in r.url and r.status in (200,201),timeout=150000) as uploaded:
   page.locator('input[type=file]').first.set_input_files({'name':'validacao-processo.pdf','mimeType':'application/pdf','buffer':data})
  identifier=uploaded.value.json()['id']
 report['uploaded_file_id']=identifier
 for _ in range(90):
  status=page.evaluate("""async id=>{const r=await fetch('/api/v1/files/'+id+'/process/status',{headers:{Authorization:'Bearer '+localStorage.getItem('token')}});return {status:r.status,body:await r.json()};}""",identifier)
  if status['body'].get('status')=='completed':break
  if status['body'].get('status')=='failed':raise RuntimeError('PDF processing failed')
  page.wait_for_timeout(1000)
 else:raise RuntimeError('PDF processing timeout')
 report['processing_complete']=True
 for maximum in [None,4096]:
  result=page.evaluate("""async ({id,maximum})=>{const body={model:'auto',stream:false,messages:[{role:'user',content:'analise o processo anexo e verifique o que devo fazer'}],files:[{type:'file',id,name:'validacao-processo.pdf'}]};if(maximum)body.params={max_tokens:maximum};const r=await fetch('/api/chat/completions',{method:'POST',headers:{Authorization:'Bearer '+localStorage.getItem('token'),'Content-Type':'application/json'},body:JSON.stringify(body)});const raw=await r.text();let value={};try{value=JSON.parse(raw)}catch{};return {http_status:r.status,budget_error:raw.includes('estimated_context_budget_exceeded'),answer_characters:value.choices?.[0]?.message?.content?.length||0,metadata:value.moara||null,error_detail:raw.includes('estimated_context_budget_exceeded')?'estimated_context_budget_exceeded':null};}""",{'id':identifier,'maximum':maximum})
  report['default' if maximum is None else 'max_tokens_4096']=result
  if fixture.get('expect_fixed'):
   assert result['http_status']==200 and not result['budget_error'],result
   assert result['metadata']['assistant']['id']=='documental',result
   assert not result['metadata']['context_management']['current_input_truncated'],result
   assert result['metadata'].get('citation_validation')=='client_source_ids_only' or result['metadata'].get('legal_verification'),result
 context.close();browser.close()
Path('/artifacts/'+('pdf-root-probe-after.json' if fixture.get('expect_fixed') else 'pdf-root-probe.json')).write_text(json.dumps(report,indent=2))
print(json.dumps(report))
