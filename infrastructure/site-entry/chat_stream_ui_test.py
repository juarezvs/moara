"""Unbuffered TLS/SSE test against the real model and authenticated chat."""
import sys,json,hashlib,time,re
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline());checks={};chats=[];errors=[];metrics={}
output=Path('/artifacts/unified-ui.json')
def checkpoint(context):
 cookie=next((c['value'] for c in context.cookies() if c['name']=='__Secure-moara_session'),None)
 output.write_text(json.dumps({'checks':checks,'metrics':metrics,'created_chats':chats,'javascript_errors':errors,'test_session_sha256':hashlib.sha256(cookie.encode()).hexdigest() if cookie else None}))
with sync_playwright() as p:
 args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']]
 if fixture.get('candidate_ip'):args+=['--host-resolver-rules=MAP moara.am.trf1.gov.br '+fixture['candidate_ip'],'--no-proxy-server']
 browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=args)
 context=browser.new_context(viewport={'width':1500,'height':950},timezone_id='America/Manaus')
 context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
 context.add_init_script("""{
 const original=window.fetch.bind(window);
 window.fetch=async(...args)=>{
   const response=await original(...args);
   if(String(args[0]).includes('/api/v1/chat/stream')&&response.body){
     const probe=window.__streamProbe;
     if(probe){probe.headers=performance.now();const reader=response.clone().body.getReader();(async()=>{try{while(true){const part=await reader.read();if(part.done)break;probe.reads.push({at:performance.now(),bytes:part.value.byteLength});}}catch(error){probe.transportEnded=error.name;}finally{probe.networkDone=true;}})();}
   }
   return response;
 };
}""")
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:180]))
 def seen(r):
  if r.request.method=='POST' and r.status==201 and r.url.endswith('/moara/api/v1/chats'):chats.append(r.json()['id']);checkpoint(context)
 page.on('response',seen)
 def start_probe():
  page.evaluate("""()=>{
   window.__streamProbe={reads:[],renders:[],networkDone:false,longTasks:[]};
   window.__streamObserver?.disconnect();
   window.__streamObserver=new MutationObserver(()=>{
     const p=window.__streamProbe;const e=document.querySelector('.message:not(.user-message):last-child .markdown');
     const length=e?.textContent?.length||0;
     if(length&&p.renders.at(-1)?.length!==length)p.renders.push({at:performance.now(),length,networkDone:p.networkDone,cursor:!!document.querySelector('.moara-typing-cursor')});
   });
   window.__streamObserver.observe(document.querySelector('.work-conversation'),{subtree:true,childList:true,characterData:true});
   window.__longTaskObserver?.disconnect();
   window.__longTaskObserver=new PerformanceObserver(list=>{window.__streamProbe.longTasks.push(...list.getEntries().map(e=>e.duration));});
   window.__longTaskObserver.observe({entryTypes:['longtask']});
  }""")
 def answer_length():return page.locator('.message:not(.user-message):last-child .markdown').evaluate('(e)=>e.textContent.length')
 try:
  page.goto('https://moara.am.trf1.gov.br/moara/chat?assistente=desenvolvedora',wait_until='domcontentloaded')
  expect(page.get_by_label('Sua mensagem',exact=True)).to_be_visible(timeout=45000);checkpoint(context)
  page.get_by_role('button',name='Opções',exact=True).click()
  page.get_by_label('Redação',exact=True).select_option('detailed')
  page.get_by_role('button',name='Opções',exact=True).click()
  question='Escreva primeiro um bloco de codigo Python com a funcao soma(a, b) que retorna a + b. Depois explique boas praticas para desenvolver software pessoal em 30 itens numerados, cada um com um pequeno paragrafo de duas frases. Inclua testes, organizacao de pastas, Git e documentacao. Nao faca perguntas e nao execute ferramentas.'
  page.get_by_label('Sua mensagem',exact=True).fill(question);start_probe()
  page.get_by_role('button',name=re.compile('Enviar solicita')).click()
  expect(page.locator('.moara-processing.is-thinking')).to_be_visible(timeout=10000)
  checks['thinking_visible_before_first_token']=True
  checks['thinking_uses_moara_mark']=page.locator('.is-thinking .processing-mark img').get_attribute('src')=='brand/mark.svg'
  page.emulate_media(reduced_motion='reduce')
  checks['thinking_respects_reduced_motion']=page.locator('.is-thinking .processing-mark').evaluate('(e)=>getComputedStyle(e,"::after").animationName==="none"') and page.locator('.is-thinking .processing-mark img').evaluate('(e)=>getComputedStyle(e).animationName==="none"')
  page.emulate_media(reduced_motion='no-preference')
  expect(page.locator('.moara-typing-cursor')).to_be_visible(timeout=180000)
  checks['cursor_visible_during_stream']=True
  for _ in range(150):
   if answer_length()>700:break
   page.wait_for_timeout(100)
  before=answer_length();checks['text_visible_before_network_completes']=not page.evaluate('window.__streamProbe.networkDone')
  page.mouse.move(1050,350);page.mouse.wheel(0,-500)
  expect(page.get_by_role('button',name=re.compile('Acompanhar resposta'))).to_be_visible(timeout=5000)
  page.wait_for_timeout(200);position=page.evaluate('scrollY')
  for _ in range(60):
   if answer_length()>before+80:break
   page.wait_for_timeout(100)
  checks['stream_keeps_growing_while_paused']=answer_length()>before
  checks['manual_reading_position_is_preserved']=abs(page.evaluate('scrollY')-position)<25
  page.get_by_role('button',name=re.compile('Acompanhar resposta')).click()
  page.wait_for_timeout(200)
  checks['resume_follows_stream_end']=page.locator('.stream-end').evaluate('(e)=>e.getBoundingClientRect().bottom<=innerHeight+24')
  checks['stream_text_is_not_hidden_by_composer']=page.locator('.moara-typing-cursor').evaluate('(e)=>e.getBoundingClientRect().bottom<document.querySelector(".work-composer-zone").getBoundingClientRect().top')
  expect(page.locator('.markdown pre code.hljs .hljs-keyword').first).to_be_visible(timeout=15000)
  checks['code_has_syntax_highlighting']=True
  page.screenshot(path='/artifacts/chat-stream-active.png',mask=[page.locator('.history-items'),page.locator('.work-user')])
  expect(page.locator('.moara-processing')).to_have_count(0,timeout=180000)
  checks['cursor_removed_on_completion']=page.locator('.moara-typing-cursor').count()==0
  original_theme=page.locator('html').get_attribute('data-theme') or 'light'
  page.evaluate('()=>document.documentElement.setAttribute("data-theme","dark")')
  checks['dark_code_theme_has_correct_background']=page.locator('.markdown pre').first.evaluate('(e)=>getComputedStyle(e).backgroundColor==="rgb(16, 28, 48)"')
  page.evaluate('(value)=>document.documentElement.setAttribute("data-theme",value)',original_theme)
  probe=page.evaluate('window.__streamProbe')
  metrics['network_reads']=len(probe['reads']);metrics['visible_updates']=len(probe['renders'])
  metrics['max_long_task_ms']=max(probe['longTasks'],default=0)
  checks['real_sse_arrives_in_multiple_reads']=len(probe['reads'])>5
  checks['response_renders_incrementally']=len(probe['renders'])>5 and any(not r['networkDone'] for r in probe['renders'])
  checks['rendering_has_no_500ms_main_thread_stall']=metrics['max_long_task_ms']<500
  page.screenshot(path='/artifacts/chat-stream-completed.png',mask=[page.locator('.history-items'),page.locator('.work-user')],mask_color='#162d3e')
  # Cancel a second real generation after its first tokens.
  page.get_by_label('Sua mensagem',exact=True).fill('Explique em 50 itens as etapas para desenvolver um jogo de tabuleiro pessoal em Python. Cada item deve ter tres frases. Nao use ferramentas.')
  page.get_by_role('button',name=re.compile('Enviar solicita')).click()
  expect(page.locator('.moara-typing-cursor')).to_be_visible(timeout=180000)
  page.get_by_role('button',name='Interromper',exact=True).click()
  expect(page.locator('.moara-processing')).to_have_count(0,timeout=30000)
  checks['cancel_preserves_received_text']=answer_length()>0
  checks['cancel_is_marked_interrupted']=page.get_by_text('Resposta interrompida',exact=True).count()==1
  checks['cancel_removes_cursor']=page.locator('.moara-typing-cursor').count()==0
  page.emulate_media(reduced_motion='reduce')
  checks['reduced_motion_is_supported']=page.evaluate('matchMedia("(prefers-reduced-motion: reduce)").matches')
  page.set_viewport_size({'width':390,'height':844})
  checks['mobile_has_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
  checks['no_javascript_errors']=not errors
 finally:
  try:
   checks['test_chats_archived']=page.evaluate("""async(ids)=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();let ok=true;for(const id of ids){const r=await fetch('/moara/api/v1/chats/'+id+'/archive',{method:'POST',headers:{'X-Moara-CSRF':me.csrf_token}});ok=ok&&r.ok;}return ok;}""",chats)
  finally:checkpoint(context);context.close();browser.close()
print(json.dumps({'checks':checks,'metrics':metrics}));assert checks and all(checks.values()),checks
