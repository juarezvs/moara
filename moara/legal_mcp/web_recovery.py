"""Bounded recovery: search snippets are leads, never normative evidence."""
import asyncio,base64,gzip,hashlib,re,time,os
from datetime import datetime,timezone
from urllib.parse import urlsplit
from xml.etree import ElementTree
import httpx
from .contracts import SubjectSearch,Norm,identify,today
from .discovery import discover,norm_link,key
from .texts import folded

def has_text(package):
 return any(e.get('device')!='identificacao' and len(e.get('text',''))>=40 for r in package.get('norms',[])+package.get('precedents',[]) for e in r.get('excerpts',[]))

def relevant_hint(title,description,topic):
 stop={'como','funciona','criterios','usar','modalidade','sobre','fonte','oficial','texto','atualizado','legislacao'}
 terms={t[:7] for t in re.findall(r'[a-z]{4,}',folded(topic)) if t not in stop}
 words={t[:7] for t in re.findall(r'[a-z]{4,}',folded(title+' '+description))}
 return bool(terms) and len(terms&words)>=min(2,len(terms))

def has_topic_text(package,topic):
 return has_text(package) and (not topic or any(e.get('device')!='identificacao' and relevant_hint(e.get('text',''),'',topic) for r in package.get('norms',[])+package.get('precedents',[]) for e in r.get('excerpts',[])))

async def web_references(client,topic,norms):
 from .web_search import references as searx_references
 searx=await searx_references(client,topic,norms)
 if searx['hints']:return searx
 from .google_discovery import references
 google=await references(client,topic,norms)
 if google['hints']:
  google['attempts']=[{k:v for k,v in google.items() if k not in ('hints','snapshots','attempts')}]
  return google
 fallback=await bing_references(client,topic,norms)
 fallback['attempts']=[{k:v for k,v in google.items() if k not in ('hints','snapshots')},{'provider':fallback['provider'],'status':fallback['status']}]
 return fallback

async def bing_references(client,topic,norms):
 if topic:SubjectSearch(query=topic)
 labels=[n.kind+' '+str(n.number)+'/'+str(n.year) for n in norms[:2]]
 if not topic and not labels:return {'status':'no_public_query','hints':[],'snapshots':[],'normative_evidence':False}
 query=' '.join([topic,*labels,'legislação fonte oficial']).strip()
 result={'status':'search_unavailable','provider':'bing_public_rss','query':query,'hints':[],'snapshots':[],'normative_evidence':False,'gaps':[]}
 if not hasattr(client,'_moara_web_slots'):client._moara_web_slots=asyncio.Semaphore(1)
 try:
  async with client._moara_web_slots:
   async with client.stream('GET','https://www.bing.com/search',params={'q':query,'format':'rss'},follow_redirects=False,timeout=10,headers={'User-Agent':'Moara-LegalResearch/0.6','Accept':'application/rss+xml,application/xml','Cache-Control':'no-cache'}) as response:
    response.raise_for_status();raw=bytearray()
    async for b in response.aiter_bytes():
     raw.extend(b)
     if len(raw)>1024*1024:raise ValueError('search_result_too_large')
    raw=bytes(raw)
    result['snapshots'].append({'url':str(response.url),'retrieved_at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(raw).hexdigest(),'snapshot_gzip_base64':base64.b64encode(gzip.compress(raw,mtime=0)).decode(),'bytes':len(raw),'content_type':response.headers.get('content-type'),'role':'discovery_only_not_legal_evidence'})
  if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('unsafe_search_xml')
  root=ElementTree.fromstring(raw)
  if root.tag!='rss':raise ValueError('not_search_rss')
  for item in root.findall('./channel/item')[:10]:
   title=item.findtext('title','')[:500];description=item.findtext('description','')[:1800];url=item.findtext('link','');u=urlsplit(url)
   if u.scheme!='https' or not u.hostname or u.username or u.password or u.port not in (None,443):continue
   text=re.sub(r'(?<=\d)\.(?=\d)','',title+' '+description)
   pertinent=relevant_hint(title,description,topic) if topic else any(re.search(r'\b'+str(n.number)+r'\b',text) and str(n.year) in text for n in norms)
   if not pertinent:continue
   # External pages are not fetched. Only references from search snippets become search leads.
   result['hints'].append({'title':title,'description':description,'url':url,'role':'unverified_search_lead'})
  result['status']='search_leads_retrieved' if result['hints'] else 'no_relevant_search_leads'
 except (httpx.HTTPError,ValueError,ElementTree.ParseError):result['gaps'].append('Busca web indisponível, resposta inválida ou sem referências pertinentes; nenhum resultado foi aceito como texto de lei.')
 return result

def hinted_norms(hints):
 result=[]
 for hint in hints:
  u=hint['url'];n=norm_link(u.replace('-normaatualizada-','-norma-'))
  try:found=([n] if n else [])+identify(hint['title']+' '+hint['description'])
  except ValueError:found=[n] if n else []
  for n in found:
   n=n.model_copy(update={'articles':[]})
   if not any(key(x.model_dump())==key(n.model_dump()) for x in result):result.append(n)
 return result[:3]

async def current_web_links(client,spec,hints,trace):
 from .sources import OfficialSources
 from .catalog import tracked
 from .texts import LegalHTML,articles_from_html,relevant
 if spec.reference_date!=today():return []
 records=[];adapter=OfficialSources(client)
 for hint in hints[:5]:
  url=hint['url']
  if urlsplit(url).hostname=='www2.camara.leg.br' and url.endswith('-normaatualizada-pl.pdf'):
   url=url[:-4]+'.html'  # Candidate counterpart; only a successful fetch confirms it.
  n=norm_link(url.replace('-normaatualizada-','-norma-'))
  if not n:continue
  if n.year>spec.reference_date.year:continue
  if spec.norms and not any(key(x.model_dump())==key(n.model_dump()) for x in spec.norms):continue
  n=next((x for x in spec.norms if key(x.model_dump())==key(n.model_dump())),n)
  record={'norm':n.model_dump(),'source':url,'status':'unavailable','excerpts':[],'snapshots':[],'source_checks':[],'gaps':[]}
  try:
   html=await tracked(adapter,url,record,'html')
   if '-normaatualizada-' not in url:
    from urllib.parse import urljoin
    prefix=url.rsplit('-norma-',1)[0]+'-normaatualizada-'
    links=[urljoin(url,v) for v in re.findall(r'href=["\']([^"\']+normaatualizada[^"\']+\.html)["\']',html,re.I)]
    links=[u for u in links if u.startswith(prefix) and urlsplit(u).hostname=='www2.camara.leg.br']
    if len(set(links))!=1:continue
    url=links[0];html=await tracked(adapter,url,record,'html')
   head=re.sub(r'(?<=\d)\.(?=\d)','',LegalHTML(html).text()[:6000])
   if not re.search(r'\b'+str(n.number)+r'\b',head) or str(n.year) not in head:continue
   record.update(source=url,status='official_text_retrieved',excerpts=relevant(articles_from_html(html,url,n.articles,spec.reference_date),spec.subject_query or spec.query))
   record['gaps'].append('Compilação atual recuperada por referência encontrada na web e identidade conferida na fonte oficial. Não comprova redação histórica nem todos os efeitos judiciais.')
   if has_topic_text({'norms':[record]},spec.subject_query):records.append(record)
  except (httpx.HTTPError,ValueError,TypeError):trace['steps'].append({'operation':'official_link_from_web','status':'unavailable'})
  if len(records)==2:break
 return records

async def recover(client,spec):
 from .research import research
 trace={'attempted':True,'status':'no_official_text','steps':[],'snapshots':[],'catalogue_discoveries':[],'web_search':None,'untrusted_text_used_as_law':False}
 empty={'status':'official_research_unavailable','reference_date':str(spec.reference_date),'checked_at':datetime.now(timezone.utc).isoformat(),'legal_conclusion_allowed':False,'norms':[],'precedents':[],'gaps':[],'recovery':trace}
 if spec.reference_date>today():empty['gaps']=['Não é possível confirmar antecipadamente uma redação futura.'];return empty
 topics=spec.recovery_topics or ([spec.subject_query] if spec.subject_query else [])
 topic=topics[0] if topics else ''
 # Public web discovery must not wait behind unrelated catalogue candidates.
 # Preserve the full subject and its official vocabulary; never guess a law number.
 if os.getenv('MOARA_SEARXNG_URL') and not spec.norms and (spec.subject_query or topic):
  from .discovery import career_query,query_variants
  public=spec.subject_query or topic
  canonical=query_variants(public)[0] if career_query(public) else public
  trace['web_search']=await web_references(client,public,[])
  records=await current_web_links(client,spec.model_copy(update={'subject_query':canonical}),trace['web_search']['hints'],trace)
  if records:
   trace['status']='official_text_recovered';empty.update(status='official_sources_retrieved',norms=records);return empty
 norms=list(spec.norms);tried=set()
 async def try_norms(items,step):
  wanted=[n for n in items if n.year<=spec.reference_date.year and key(n.model_dump()) not in tried][:2]
  if not wanted:return None
  tried.update(key(n.model_dump()) for n in wanted)
  try:
   package=await asyncio.wait_for(research(client,spec.model_copy(update={'norms':wanted,'subject_query':topic})),28)
   trace['steps'].append({'operation':step,'norms':[n.model_dump() for n in wanted],'text_retrieved':has_topic_text(package,topic)})
   if has_topic_text(package,topic):trace['status']='official_text_recovered';package['recovery']=trace;return package
   trace['snapshots'].extend(s for r in package.get('norms',[]) for s in r.get('snapshots',[]))
  except (httpx.HTTPError,ValueError,KeyError,TypeError,TimeoutError):trace['steps'].append({'operation':step,'status':'unavailable'})
  return None
 if topic:
  try:
   found=await asyncio.wait_for(discover(client,SubjectSearch(query=topic)),18)
   trace['catalogue_discoveries'].append({k:v for k,v in found.items() if k!='snapshots'})
   trace['snapshots'].extend(found.get('snapshots',[]));trace['steps'].append({'operation':'focused_official_catalogue','topic':topic,'status':found['status']})
   # Exact user-supplied references remain authoritative over newly suggested norms.
   if not norms:norms=[Norm.model_validate(r['norm']) for r in found['candidates'][:2]]
  except (httpx.HTTPError,ValueError,KeyError,TypeError,TimeoutError):trace['steps'].append({'operation':'focused_official_catalogue','status':'unavailable'})
 package=await try_norms(norms,'official_text_after_focused_search')
 if package:return package
 trace['web_search']=await web_references(client,spec.subject_query or topic,spec.norms)
 records=await current_web_links(client,spec,trace['web_search']['hints'],trace)
 if records:
  trace['status']='official_text_recovered';empty.update(status='official_sources_retrieved',norms=records);return empty
 leads=hinted_norms(trace['web_search']['hints'])
 if spec.norms:
  allowed={key(n.model_dump()) for n in spec.norms};leads=[n for n in leads if key(n.model_dump()) in allowed]
 package=await try_norms(leads,'verify_web_leads_in_official_sources')
 if package:return package
 empty['gaps'].append('A busca reformulada e as referências web não forneceram texto oficial suficiente. Um resultado de buscador não foi usado como substituto da fonte oficial.')
 return empty
