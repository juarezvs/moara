import sys,json
from pathlib import Path
from playwright.sync_api import sync_playwright
fixture=json.loads(sys.stdin.readline());report={}
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']])
 context=browser.new_context(viewport={'width':1280,'height':900})
 context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
 page=context.new_page();page.goto('https://moara.am.trf1.gov.br/',wait_until='domcontentloaded');page.wait_for_selector('#chat-input',timeout=30000)
 for question in ['quais suas habilidades?','o que você pode fazer?']:
  result=page.evaluate("""async question=>{const r=await fetch('/api/chat/completions',{method:'POST',headers:{Authorization:'Bearer '+localStorage.getItem('token'),'Content-Type':'application/json'},body:JSON.stringify({model:'auto',stream:false,messages:[{role:'user',content:'Lei 14133/2021 art.6'},{role:'assistant',content:'Informe a data'},{role:'user',content:question}]})});const v=await r.json();return {status:r.status,reason:v.moara?.reason,capabilities:v.choices?.[0]?.message?.content?.includes('seis especialidades')};}""",question)
  assert result=={'status':200,'reason':'institutional_identity','capabilities':True},result
  report[question]=True
 result=page.evaluate("""async id=>{const messages=[{role:'user',content:'Informação de conversa antiga sem relação com o anexo. '.repeat(500)},{role:'assistant',content:'Resposta anterior de teste sem conteúdo processual. '.repeat(400)},{role:'user',content:'analise o processo anexo e verifique o que devo fazer'}];const r=await fetch('/api/chat/completions',{method:'POST',headers:{Authorization:'Bearer '+localStorage.getItem('token'),'Content-Type':'application/json'},body:JSON.stringify({model:'auto',stream:false,messages,files:[{type:'file',id,name:'validacao-processo.pdf'}]})});const v=await r.json();return {status:r.status,metadata:v.moara,notice_visible:v.choices?.[0]?.message?.content?.includes('mensagens anteriores ficaram fora do contexto')};}""",fixture['existing_file_id'])
 assert result['status']==200,result
 if result['metadata']['context_management']['omitted_messages']:
  assert result['notice_visible'],result
 assert result['metadata']['context_management']['current_input_truncated'] is False
 report['long_history_document_analysis']=result
 context.close();browser.close()
Path('/artifacts/chat-repair-root-smoke.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
