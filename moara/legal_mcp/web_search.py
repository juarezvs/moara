"""SearXNG discovery + bounded, DNS-pinned public HTTPS extraction."""
import asyncio,base64,gzip,hashlib,ipaddress,json,os,re,socket
from datetime import datetime,timezone
from urllib.parse import urlsplit,urlunsplit,urljoin
import httpx
from pydantic import BaseModel,ConfigDict,Field,field_validator
from moara.research_browser.policy import RobotsRules,candidate_url,AGENT

class WebSearch(BaseModel):
 model_config=ConfigDict(extra='forbid')
 query:str=Field(min_length=2,max_length=180)
 max_results:int=Field(default=3,ge=1,le=5)
 official_only:bool=False
 urls:list[str]=Field(default_factory=list,max_length=3)
 @field_validator('query')
 @classmethod
 def public_query(cls,value):
  value=' '.join(value.split())
  if re.search(r'@|\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b|\b\d{7}-\d{2}\.\d{4}|(?:senha|password|token|cpf|cnpj|sigiloso|confidencial)\b',value,re.I):
   raise ValueError('public_query_required')
  if len(value.split())>24 or any(ord(c)<32 for c in value):raise ValueError('public_query_required')
  return value
 @field_validator('urls')
 @classmethod
 def public_urls(cls,values):return [validate_url(url) for url in values]

def validate_url(value):
 u=urlsplit(value)
 if u.scheme!='https' or not u.hostname or u.username is not None or u.password is not None or u.port not in (None,443) or len(value)>2000:
  raise ValueError('public_https_url_required')
 host=u.hostname.casefold()
 if '.' not in host or host.endswith(('.local','.localhost','.internal','.invalid')) or re.search(r'[%\\\x00-\x20]',host):
  raise ValueError('public_hostname_required')
 try:
  if not ipaddress.ip_address(host).is_global:raise ValueError('private_destination')
 except ValueError as exc:
  if str(exc)=='private_destination':raise
 return urlunsplit(('https',u.netloc,u.path or '/',u.query,''))

def official_host(url):
 host=urlsplit(url).hostname or ''
 return host.endswith(('.gov.br','.jus.br','.leg.br')) or host in {'gov.br','jus.br','leg.br'}

async def public_address(host):
 rows=await asyncio.get_running_loop().getaddrinfo(host,443,type=socket.SOCK_STREAM)
 addresses=list(dict.fromkeys(r[4][0] for r in rows))
 if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):raise ValueError('private_dns_destination')
 return next((a for a in addresses if ':' not in a),addresses[0])

async def download(client,url,limit=1048576):
 """Keep the validated IP in the actual connection; SNI/TLS and Host remain original."""
 original=validate_url(url)
 for redirect in range(3):
  u=urlsplit(original);ip=await asyncio.wait_for(public_address(u.hostname),5)
  netloc='['+ip+']' if ':' in ip else ip
  pinned=urlunsplit(('https',netloc,u.path,u.query,''))
  async with client.stream('GET',pinned,extensions={'sni_hostname':u.hostname},
   headers={'Host':u.hostname,'User-Agent':AGENT,'Connection':'close','Cookie':'','Accept':'text/html,text/plain;q=0.9','Cache-Control':'no-cache'},
   timeout=10,follow_redirects=False) as response:
   if response.status_code in (301,302,303,307,308):
    if redirect==2:raise ValueError('redirect_limit')
    original=validate_url(urljoin(original,response.headers.get('location','')));continue
   raw=bytearray()
   async for block in response.aiter_bytes():
    raw.extend(block)
    if len(raw)>limit:raise ValueError('public_page_too_large')
   return original,response.status_code,bytes(raw),dict(response.headers)
 raise ValueError('redirect_limit')

async def extract_page(client,url,query,depth=0):
 if depth>2:raise ValueError('cross_host_redirect_limit')
 url=validate_url(url);u=urlsplit(url)
 # Deny extraction if robots policy cannot be checked. Never solve/bypass challenges.
 robots_url='https://'+u.netloc+'/robots.txt'
 _,status,robots,_=await download(client,robots_url,262144)
 if status in (401,403) or status>=500 or status not in (200,404,410):raise ValueError('robots_unavailable_or_denied')
 rules=RobotsRules(robots.decode('utf8',errors='replace') if status==200 else '')
 if not rules.can_fetch(AGENT,url):raise ValueError('robots_disallowed')
 final,status,raw,headers=await download(client,url)
 if urlsplit(final).hostname!=u.hostname:
  # Cross-host redirects require their own robots policy.
  return await extract_page(client,final,query,depth+1)
 if status!=200:raise ValueError('page_http_'+str(status))
 kind=headers.get('content-type','').casefold()
 if not any(t in kind for t in ('text/html','text/plain','application/xhtml+xml')):raise ValueError('unsupported_page_type')
 from trafilatura import extract
 text=await asyncio.to_thread(extract,raw,url=final,output_format='txt',include_comments=False,include_tables=True,favor_recall=True)
 if not text or len(text.strip())<100:raise ValueError('insufficient_page_text')
 text=text.strip()
 if re.search(r'just a moment|verify you are human|access denied|checking your browser',text[:400],re.I):raise ValueError('provider_access_restricted')
 paragraphs=[p.strip() for p in text.splitlines() if p.strip()]
 terms=set(re.findall(r'[^\W\d_]{3,}',query.casefold()))
 scored=sorted(enumerate(paragraphs),key=lambda row:sum(t in row[1].casefold() for t in terms),reverse=True)
 chosen=set(i for i,_ in scored[:14]);excerpt='\n'.join(p for i,p in enumerate(paragraphs) if i in chosen)[:9000]
 if len(excerpt)<100:excerpt=text[:9000]
 return {'url':final,'official_domain':official_host(final),'retrieved_at':datetime.now(timezone.utc).isoformat(),
  'sha256':hashlib.sha256(raw).hexdigest(),'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'bytes':len(raw),
  'excerpt':excerpt,'text_characters':len(text),'excerpt_truncated':len(excerpt)<len(text),
  'extractor':'trafilatura-2.3.1','content_type':kind,'last_modified':headers.get('last-modified'),
  'snapshot_gzip_base64':base64.b64encode(gzip.compress(raw,mtime=0)).decode(),
  'robots_sha256':hashlib.sha256(robots).hexdigest(),'claim_veracity':'not_certified','legal_vigency':'not_certified'}

async def references(client,topic,norms=()):
 labels=[n.kind+' '+str(n.number)+'/'+str(n.year) for n in norms[:2]]
 query=' '.join([topic,*labels]).strip()
 result={'provider':'searxng_self_hosted','status':'not_configured','hints':[],'snapshots':[],'normative_evidence':False,'gaps':[]}
 endpoint=os.getenv('MOARA_SEARXNG_URL','')
 if endpoint!='http://moara-searxng:8080':return result
 from .discovery import career_query,query_variants
 if career_query(query):query=query_variants(query)[0]
 spec=WebSearch(query=('legislacao lei '+query)[:180])
 try:
  response=await client.get(endpoint+'/search',params={'q':spec.query,'format':'json','language':'pt-BR','safesearch':1},timeout=18)
  response.raise_for_status();value=response.json()
  result['unresponsive_engines']=value.get('unresponsive_engines',[])
  for row in value.get('results',[])[:40]:
   url=candidate_url(str(row.get('url','')))
   if url:result['hints'].append({'url':url,'title':str(row.get('title',''))[:400],'description':str(row.get('content',''))[:800],'role':'unverified_search_lead'})
  result['hints']=list({r['url']:r for r in result['hints']}.values())[:10]
  result['status']='candidates_found' if result['hints'] else 'no_official_candidates'
 except (httpx.HTTPError,ValueError,TypeError):result['status']='search_unavailable'
 return result

async def search(client,spec):
 report={'provider':'searxng_self_hosted','checked_at':datetime.now(timezone.utc).isoformat(),'status':'no_verified_content',
         'query':spec.query,'candidates':[],'sources':[],'gaps':[],'normative_evidence':False,'legal_conclusion_allowed':False}
 endpoint=os.getenv('MOARA_SEARXNG_URL','')
 if endpoint!='http://moara-searxng:8080':
  report['gaps'].append('Serviço de pesquisa não configurado.');return report
 urls=list(spec.urls)
 if not urls:
  try:
   response=await client.get(endpoint+'/search',params={'q':spec.query,'format':'json','language':'pt-BR','safesearch':1},timeout=18)
   response.raise_for_status();data=response.json()
   report['unresponsive_engines']=data.get('unresponsive_engines',[])
   for item in data.get('results',[])[:30]:
    try:url=validate_url(str(item.get('url','')))
    except ValueError:continue
    if spec.official_only and not official_host(url):continue
    if url in urls:continue
    urls.append(url);report['candidates'].append({'url':url,'title':str(item.get('title',''))[:400],'snippet':str(item.get('content',''))[:600],'role':'unverified_search_lead'})
    if len(urls)>=spec.max_results+2:break
  except (httpx.HTTPError,ValueError,TypeError):
   report['gaps'].append('Pesquisa indisponível; não foram usados resultados inventados.');return report
 if not hasattr(client,'_moara_public_read_slots'):client._moara_public_read_slots=asyncio.Semaphore(2)
 slots=client._moara_public_read_slots
 async def read(url):
  async with slots:
   try:
    if spec.official_only and not official_host(url):raise ValueError('official_domain_required')
    return await asyncio.wait_for(extract_page(client,url,spec.query),24)
   except (httpx.HTTPError,ValueError,OSError,TimeoutError) as exc:
    return {'url':url,'error':str(exc)[:80] if isinstance(exc,ValueError) else type(exc).__name__}
 results=await asyncio.gather(*(read(url) for url in urls[:spec.max_results+2]))
 for item in results:
  if 'excerpt' in item and spec.official_only and not item['official_domain']:report['gaps'].append({'url':item['url'],'reason':'redirect_to_non_official_domain'})
  elif 'excerpt' in item and len(report['sources'])<spec.max_results:report['sources'].append(item)
  elif 'error' in item:report['gaps'].append({'url':item['url'],'reason':item['error']})
 if report['sources']:report['status']='retrieved_content'
 report['gaps'].append('Resultados de busca são candidatos. Domínio oficial e extração não certificam a veracidade de toda afirmação nem vigência jurídica.')
 return report
