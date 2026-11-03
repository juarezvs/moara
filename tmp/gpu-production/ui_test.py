"""Run the existing web application in an isolated, sandboxed test browser."""
import sys,json,time,base64,hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline())
checks={};errors=[];routing={};created=[]
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']])
 context=browser.new_context(viewport={'width':1440,'height':1000})
 context.add_init_script("if(location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
 context.add_init_script("""window.__gpuTestRouting=null; const originalFetch=window.fetch.bind(window);
 window.fetch=async (...args)=>{const response=await originalFetch(...args);
 if(String(args[0]).includes('/moara/api/v1/chat/stream')){
 response.clone().text().then(text=>{for(const line of text.split('\\n')){
 if(line.startsWith('data: ')){try{const row=JSON.parse(line.slice(6));if(row.moara)window.__gpuTestRouting=row.moara;}catch{}}}}).catch(()=>{});}
 return response;};""")
 page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)[:200]))
 def response_seen(response):
  if response.request.method=='POST' and response.url.endswith('/moara/api/v1/chats') and response.status==201:
   created.append(response.json()['id'])
 page.on('response',response_seen)
 page.goto('https://moara.am.trf1.gov.br/moara/chat',wait_until='networkidle')
 expect(page.get_by_role('heading',name='Como posso ajudar você hoje?')).to_be_visible(timeout=30000)
 checks['interactive_authentication_bridge']=True
 page.get_by_label('Sua mensagem',exact=True).fill('Validação técnica inteiramente fictícia: a equipe Aurora responde em sete dias úteis. Informe somente esse prazo.')
 started=time.monotonic()
 with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/moara/api/v1/chat/stream'),timeout=90000) as response_info:
  page.get_by_role('button',name='Enviar ↑',exact=True).click()
 response=response_info.value
 expect(page.locator('.message:not(.user-message) .markdown').last).to_contain_text('dias úteis',timeout=90000)
 expect(page.get_by_role('button',name='Gerar novamente',exact=True)).to_be_visible(timeout=15000)
 elapsed=time.monotonic()-started
 page.wait_for_function("window.__gpuTestRouting?.execution_backend === 'gpu'",timeout=15000)
 routing=page.evaluate('window.__gpuTestRouting')
 checks['chat_answer_rendered']=True
 checks['gpu_used_from_browser']=routing.get('execution_backend')=='gpu'
 checks['model_visible']=page.get_by_role('status').filter(has_text='Gemma 4 12B').count()>0
 page.locator('.chat-panel').screenshot(path='/artifacts/moara-gpu-chat.png')
 # Remove only the conversation created by this disposable test context.
 removed=page.evaluate("""async ids=>{const me=await (await fetch('/moara/api/v1/auth/me')).json();
 for(const id of ids){const r=await fetch('/moara/api/v1/chats/'+id,{method:'DELETE',headers:{'X-Moara-CSRF':me.csrf_token}});if(!r.ok)return false;}return true;}""",created)
 assert removed
 checks['synthetic_chat_removed']=bool(created)
 checks['no_javascript_errors']=not errors
 session=next(cookie['value'] for cookie in context.cookies() if cookie['name']=='__Secure-moara_session')
 session_hash=hashlib.sha256(session.encode()).hexdigest()
 context.close();browser.close()
report={'checks':checks,'routing':routing,'seconds_from_send_to_rendered_answer':elapsed,'javascript_errors':errors,'synthetic_only':True,'test_session_sha256':session_hash}
Path('/artifacts/moara-gpu-ui.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='test_session_sha256'},ensure_ascii=False),flush=True)
assert all(checks.values())
