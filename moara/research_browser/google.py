"""Browser discovery stops at site restrictions, login or anti-automation challenges."""
import asyncio,time,urllib.request
from datetime import datetime,timezone
from urllib.parse import urlsplit,urlunsplit
from .policy import AGENT,robot_policy,search_url,network_permission,candidate_url

def fetch_robots():
 request=urllib.request.Request('https://www.google.com/robots.txt',headers={'User-Agent':AGENT})
 with urllib.request.urlopen(request,timeout=8) as response:
  if response.url!='https://www.google.com/robots.txt':raise ValueError('unexpected_robots_redirect')
  raw=response.read(262145)
  if response.status!=200 or len(raw)>262144:raise ValueError('invalid_robots_response')
  return raw

async def discover(topic):
 result={'provider':'google_ai_mode_browser','status':'search_unavailable','hints':[],'normative_evidence':False,'gaps':[],'checked_at':datetime.now(timezone.utc).isoformat(),'robots':None,'navigation_checks':[],'generated_answer_used':False}
 phase='access_policy'
 try:
  raw=await asyncio.to_thread(fetch_robots);rules,proof=robot_policy(raw);result['robots']=proof
  target=search_url(topic)
  if not network_permission(target,rules,True):
   result.update(status='provider_access_restricted',gaps=['As instruções públicas do Google não permitem automatizar esta rota.']);return result
  from playwright.async_api import async_playwright
  async with async_playwright() as p:
   phase='sandboxed_browser_start'
   browser=await p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage'])
   try:
    context=await browser.new_context(service_workers='block',accept_downloads=False,locale='pt-BR')
    await context.clear_permissions()
    blocked=[]
    async def route_handler(route):
     request=route.request;navigation=request.is_navigation_request()
     if not network_permission(request.url,rules,navigation):
      if navigation:
       u=urlsplit(request.url);blocked.append({'url':urlunsplit((u.scheme,u.netloc,u.path,'','')),'reason':'provider_route_not_permitted'})
      await route.abort();return
     if request.resource_type in {'image','font','media'}:await route.abort();return
     await route.continue_()
    await context.route('**/*',route_handler)
    page=await context.new_page()
    phase='google_navigation'
    try:await page.goto(target,wait_until='domcontentloaded',timeout=20000)
    except Exception:
     if not blocked:raise
    if blocked:
     result.update(status='provider_access_restricted',navigation_checks=blocked[:5],gaps=['A entrada do Modo IA redirecionou para uma rota não permitida para automação ou para acesso interativo.']);return result
    # A bounded observation period, not repeated requests or challenge solving.
    phase='observe_candidate_links'
    for _ in range(6):
     text=(await page.locator('body').inner_text(timeout=3000))[:24000].casefold()
     if any(t in text for t in ['unusual traffic','tráfego incomum','não sou um robô','verify you are human']):
      result.update(status='interactive_access_required',gaps=['Google solicitou verificação humana; a consulta automática foi interrompida.']);return result
     if urlsplit(page.url).hostname!='www.google.com':
      result.update(status='interactive_access_required',gaps=['Google solicitou uma etapa externa de acesso; a consulta foi interrompida.']);return result
     links=await page.locator('a[href]').evaluate_all('(nodes)=>nodes.slice(0,250).map(a=>({url:a.href,title:(a.textContent||a.getAttribute("aria-label")||"").trim().slice(0,500)}))')
     seen=set()
     for link in links:
      url=candidate_url(link['url'])
      if not url or url in seen:continue
      seen.add(url);result['hints'].append({'url':url,'title':link['title'],'description':'','role':'unverified_search_lead'})
      if len(result['hints'])>=8:break
     if result['hints']:
      result['status']='search_leads_retrieved';return result
     await asyncio.sleep(.5)
    result.update(status='no_official_search_leads',gaps=['O navegador não recuperou links oficiais utilizáveis; a resposta gerada do Google não foi usada como evidência.'])
   finally:await browser.close()
 except Exception as error:
  result.update(failure_stage=phase,failure_kind=type(error).__name__)
  result['gaps'].append('Navegador ou provedor indisponível; nenhuma resposta do Google foi aceita como fonte jurídica.')
 return result
