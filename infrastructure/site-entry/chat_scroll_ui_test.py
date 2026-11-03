"""Exercise scrolling with controlled streams and real native persistence/auth."""
import sys,json,hashlib,re
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline());checks={};chats=[];resources=[];errors=[];rbac_accounts=[]
output=Path('/artifacts/unified-ui.json')
def configure(context):
 if fixture.get('proxy'):
  def proxy(route):
   u=urlsplit(route.request.url)
   try:response=route.fetch(url='http://'+fixture['proxy']+':8080'+u.path+('?' +u.query if u.query else ''),max_redirects=0,timeout=180000)
   except Exception:raise RuntimeError('Candidate proxy failed; sensitive headers suppressed') from None
   route.fulfill(response=response)
  context.route('https://moara.am.trf1.gov.br/**',proxy)
def checkpoint(context):
 cookie=next((c['value'] for c in context.cookies() if c['name']=='__Secure-moara_session'),None)
 output.write_text(json.dumps({'checks':checks,'created_chats':chats,'created_resources':resources,'created_rbac_accounts':rbac_accounts,'test_session_sha256':hashlib.sha256(cookie.encode()).hexdigest() if cookie else None,'javascript_errors':errors}))
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']])
 context=browser.new_context(viewport={'width':1600,'height':1100},timezone_id='America/Manaus');configure(context)
 context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
 context.add_init_script("""(() => {
 const original=window.fetch.bind(window);window.__moaraOriginalFetch=original;window.__scrollRequests=0;
 window.fetch=(input,options)=>{
  const url=typeof input==='string'?input:input.url;
  if(new URL(url,location.href).pathname!=='/moara/api/v1/chat/stream')return original(input,options);
  window.__scrollRequests++;
  return Promise.resolve(new Response(new ReadableStream({start(controller){
   window.__scrollStream=controller;
   options?.signal?.addEventListener('abort',()=>{try{controller.error(new DOMException('Aborted','AbortError'));}catch{}},{once:true});
  }}),{headers:{'Content-Type':'text/event-stream'}}));
 };
})();""")
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:160]))
 def seen(r):
  if r.request.method=='POST' and r.status==201 and r.url.endswith('/moara/api/v1/chats'):chats.append(r.json()['id']);checkpoint(context)
 page.on('response',seen)
 def wait_stream(n):
  for _ in range(200):
   if page.evaluate('window.__scrollRequests||0')>=n:return
   page.wait_for_timeout(50)
  raise AssertionError('Controlled request was not opened')
 def emit(text,done=False):
  page.evaluate(r"""({text,done})=>{const c=window.__scrollStream;const e=new TextEncoder();if(text)c.enqueue(e.encode('data: '+JSON.stringify({choices:[{delta:{content:text}}]})+'\n\n'));if(done){c.enqueue(e.encode('data: [DONE]\n\n'));c.close();}}""",{'text':text,'done':done})
 def begin(text,n):
  page.get_by_label('Sua mensagem',exact=True).fill(text);page.get_by_role('button',name=re.compile('Enviar solicita')).click();wait_stream(n);expect(page.locator('.moara-processing')).to_be_visible();page.wait_for_timeout(100)
 def reply_visible():
  r=page.locator('.work-conversation .message:not(.user-message)>strong').last.bounding_box();h=page.locator('.moara-site-header').bounding_box()
  return r is not None and r['y']>=h['y']+h['height']-2 and r['y']<h['y']+h['height']+220
 def progress_visible():
  r=page.locator('.moara-processing').bounding_box();h=page.locator('.moara-site-header').bounding_box();c=page.locator('.work-composer').bounding_box()
  return r['y']>=h['y']+h['height'] and r['y']+r['height']<=min(page.viewport_size['height'],c['y'])+2
 answer='## INICIO DA RESPOSTA SINTETICA\n\n'+('\n\n'.join('Paragrafo sintetico '+str(i)+': conteudo ficticio usado apenas para validar a leitura e a rolagem.' for i in range(130)))
 try:
  page.goto('https://moara.am.trf1.gov.br/moara/chat',wait_until='domcontentloaded');expect(page.get_by_label('Sua mensagem',exact=True)).to_be_visible(timeout=45000);checkpoint(context)
  begin('Teste sintetico de rolagem.\n'+('Contexto de teste sem dados institucionais.\n'*200),1);checks['desktop_scrolls_to_real_processing_indicator']=progress_visible()
  emit(answer);expect(page.locator('.message:not(.user-message) h2')).to_have_count(1);page.wait_for_timeout(100);checks['first_content_shows_start_of_answer']=reply_visible()
  box=page.locator('.work-conversation .messages');before=box.evaluate('(e)=>e.scrollTop');emit('\n\nNovo trecho sintetico.\n\n'+'Texto adicional. '*150);page.wait_for_timeout(120)
  checks['stream_does_not_follow_every_chunk']=abs(box.evaluate('(e)=>e.scrollTop')-before)<3
  box.hover();page.mouse.wheel(0,420);page.wait_for_timeout(200);manual=box.evaluate('(e)=>e.scrollTop');checks['user_can_scroll_while_streaming']=manual>before+100
  emit('\n\nFim do teste sintetico.',True);expect(page.locator('.moara-processing')).to_have_count(0,timeout=30000);page.wait_for_timeout(100);checks['completion_respects_manual_reading']=abs(box.evaluate('(e)=>e.scrollTop')-manual)<4
  begin('Segunda pergunta sintetica para validar o inicio da resposta.',2);checks['next_question_shows_processing']=progress_visible();emit(answer,True);expect(page.locator('.moara-processing')).to_have_count(0,timeout=30000);page.wait_for_timeout(100);checks['completed_answer_returns_to_start']=reply_visible()
  page.get_by_role('button',name='Gerar novamente',exact=True).click();wait_stream(3);emit(answer+'\n\nResposta sintetica regenerada.',True);expect(page.locator('.moara-processing')).to_have_count(0,timeout=30000);page.wait_for_timeout(100);checks['regeneration_positions_answer_start']=reply_visible() and page.locator('.message:not(.user-message)').count()==2
  begin('Terceira pergunta sintetica para validar interrupcao.',4);emit('## RESPOSTA PARCIAL SINTETICA\n\nConteudo parcial que deve ser preservado.');expect(page.locator('.message:not(.user-message)').last).to_contain_text('Conteudo parcial');page.get_by_role('button',name='Interromper',exact=True).click();expect(page.locator('.moara-processing')).to_have_count(0,timeout=30000);checks['interruption_preserves_partial_response']='Resposta interrompida' in page.locator('.message:not(.user-message)').last.inner_text()
  page.set_viewport_size({'width':390,'height':844});page.reload(wait_until='domcontentloaded');expect(page.get_by_label('Sua mensagem',exact=True)).to_be_visible(timeout=45000)
  begin('Teste sintetico no celular.\n'+('Contexto ficticio para rolagem.\n'*80),1);checks['mobile_scrolls_to_processing']=progress_visible();emit(answer,True);expect(page.locator('.moara-processing')).to_have_count(0,timeout=30000);page.wait_for_timeout(120);checks['mobile_answer_starts_below_header']=reply_visible();checks['mobile_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
  start=page.evaluate('scrollY');page.mouse.wheel(0,400);page.wait_for_timeout(150);checks['mobile_user_controls_remaining_reading']=page.evaluate('scrollY')>start+100
  checks['no_javascript_errors']=not errors
 finally:
  try:
   checks['synthetic_chats_archived']=page.evaluate("""async(ids)=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();for(const id of ids){const r=await fetch('/moara/api/v1/chats/'+id+'/archive',{method:'POST',headers:{'X-Moara-CSRF':me.csrf_token}});if(!r.ok)return false;}return true;}""",chats)
  finally:checkpoint(context);context.close();browser.close()
print(json.dumps({'checks':checks,'controlled_stream_fixture':True}));assert checks and all(checks.values())
