"""Discover tribunal references by subject and read current official metadata.

Topic identity, repercussão geral, votes and final merits are separate facts.
No topic number, disease, benefit or answer is mapped in this module.
"""
import asyncio,re
from datetime import datetime,timezone
from urllib.parse import urlencode,urlsplit,urljoin,parse_qs
import httpx
from .contracts import Precedent,today
from .sources import OfficialSources,clean
from .catalog import tracked
from .texts import folded

BASE='https://portal.stf.jus.br/jurisprudenciaRepercussao/'
STOP={'tema','temas','stf','stj','pessoas','pessoa','tem','têm','ter','direito','trata','tribunal','supremo','federal','jurisprudência','jurisprudencia','sobre','garante','podem','pode','repercussão','geral','base','cálculo','calculo','fala','fale','diz'}

ACRONYMS={'hiv','icms','pis','sus','inss','ipi','iptu','iss','irpf','fgts'}
def keywords(topic):
 synonyms={'remedio':'medicamento','remedios':'medicamento','medicamentos':'medicamento'}
 stop={folded(w) for w in STOP}|{'teses','tese','respectivas','respectivos','suas','seus','sua','seu','e','de','do','da','os','as','o','a','qual','quais','que'}
 return list(dict.fromkeys(synonyms.get(folded(w),folded(w)) for w in topic.split() if folded(w) not in stop))
def searches(topic):
 words=keywords(topic)
 anchors=[w for w in words if w in ACRONYMS]
 exact=[' e '.join(words[:5])] if len(words)>=3 else []
 return list(dict.fromkeys(q for q in exact+anchors[:1]+[' ou '.join(words[:5])]+[' e '.join(words[:3])] if q))[:3]

def matches(text,topic):
 words=keywords(topic);value=folded(text)
 anchors=[w for w in words if w in ACRONYMS]
 if anchors and not any(re.search(r'\b'+re.escape(folded(w))+r'\b',value) for w in anchors):return 0
 return sum(2 if re.search(r'\b'+re.escape(folded(w))+r'\b',value) else 1 if folded(w[:6]) in value else 0 for w in words)

def listing(html,topic):
 rows=[];seen=set()
 for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',html,re.S|re.I):
  links=re.findall(r'<a\b[^>]*href=["\']([^"\']*verAndamentoProcesso\.asp\?[^"\']+)["\'][^>]*>(.*?)</a>',row,re.S|re.I)
  if not links:continue
  url=urljoin(BASE,clean(links[0][0]));u=urlsplit(url);p=parse_qs(u.query)
  if u.hostname!='portal.stf.jus.br' or u.path!='/jurisprudenciaRepercussao/verAndamentoProcesso.asp':continue
  try:n=int(p['numeroTema'][0]);ref=Precedent(court='STF',kind='TEMA',number=n)
  except (KeyError,ValueError):continue
  if n in seen:continue
  title=next((clean(body) for _,body in links if len(clean(body))>30),'')
  if not title:continue
  score=3*matches(title,topic)+matches(clean(row),topic)
  if score<=0:continue
  seen.add(n)
  rows.append({'reference':ref.model_dump(),'title':title,'source':BASE+'tema.asp?num='+str(n),'andamento_url':url,'relevance':score})
 return sorted(rows,key=lambda r:-r['relevance'])[:8]

def field(html,cls,element='p'):
 m=re.search(r'class=["\']'+re.escape(cls)+r'["\'][^>]*>.*?<'+element+r'\b[^>]*>(.*?)</'+element+'>',html,re.S|re.I)
 return clean(m[1]) if m else ''

def theme_metadata(html,number):
 marker=re.search(r'class=["\']tema-numero["\'][^>]*>.*?<a\b[^>]*>(.*?)</a>',html,re.S|re.I)
 if not marker or not re.fullmatch(r'\d+',clean(marker[1])) or int(clean(marker[1]))!=number:raise ValueError('official_theme_identity_mismatch')
 title=field(html,'tema-titulo-link','a');description=field(html,'tema-descricao')
 leading=field(html,'tema-leadingcase');status=field(html,'tema-situacao-atual')
 if not title or not description or not re.fullmatch(r'(?:RE|ARE)\s+[\d.]+',leading):raise ValueError('incomplete_official_theme')
 links=re.findall(r'href=["\']([^"\']*verAndamentoProcesso\.asp\?[^"\']+)["\']',html,re.I)
 valid=[]
 for raw in links:
  url=urljoin(BASE,clean(raw));u=urlsplit(url);params=parse_qs(u.query)
  if u.scheme=='https' and u.hostname=='portal.stf.jus.br' and not u.username and u.port in (None,443) and u.path=='/jurisprudenciaRepercussao/verAndamentoProcesso.asp' and params.get('numeroTema')==[str(number)] and params.get('numeroProcesso')==[re.sub(r'\D','',leading)]:valid.append(url)
 return {'number':number,'title':title,'description':re.sub(r'^Descrição:\s*','',description),'leading_case':leading,'reported_status':status,'andamento_url':valid[0] if valid else None,'final_merits_thesis_confirmed':False}

def events(html):
 result=[]
 for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',html,re.S|re.I):
  cells=[clean(v) for v in re.findall(r'<td\b[^>]*>(.*?)</td>',row,re.S|re.I)]
  if len(cells)<2 or not re.fullmatch(r'\d{2}/\d{2}/\d{4}',cells[0]):continue
  try:when=datetime.strptime(cells[0],'%d/%m/%Y').date()
  except ValueError:continue
  if when>today():continue
  result.append({'date':str(when),'label':cells[1],'description':' '.join(cells[2:])[:1600]})
 return sorted(result,key=lambda r:r['date'],reverse=True)[:30]

async def theme(adapter,spec,at):
 url=BASE+'tema.asp?num='+str(spec.number)
 record={'reference':spec.model_dump(),'source':url,'status':'unavailable','excerpts':[],'snapshots':[],'source_checks':[],'gaps':[]}
 if at!=today():record['gaps'].append('Consulta corrente não comprova situação histórica ou futura de um tema.');return record
 try:
  html=await tracked(adapter,url,record,'html');meta=theme_metadata(html,spec.number);record['official_theme']=meta
  text='Tema '+str(spec.number)+' do STF. Título: '+meta['title']+' Descrição: '+meta['description']+' Leading case: '+meta['leading_case']+'. Situação do cadastro: '+meta['reported_status']
  record['excerpts'].append({'device':'STF TEMA '+str(spec.number),'text':text,'source':url,'version_date':str(at),'effective_date_confirmed':False})
  if meta['andamento_url']:
   try:
    html=await tracked(adapter,meta['andamento_url'],record,'html');recent=events(html);meta['events']=recent
    pertinent=[r for r in recent if re.search(r'julgamento|julgado|suspenso|acórdão|mérito|destaque',r['label'],re.I)]
    if pertinent:meta['latest_merits_event']=pertinent[0]
    meta['movements_checked']=bool(recent)
    if recent:record['excerpts'].append({'device':'STF TEMA '+str(spec.number)+' ANDAMENTOS','text':' '.join(r['date']+' '+r['label']+'. '+r['description'] for r in recent[:4]),'source':meta['andamento_url'],'version_date':str(at),'effective_date_confirmed':False})
   except (httpx.HTTPError,ValueError):record['gaps'].append('Não foi possível conferir os andamentos; a situação do mérito permanece não confirmada.')
  record['status']='official_precedent_record_retrieved'
  from .stf_theses import attach
  try:await asyncio.wait_for(attach(adapter,record),23)
  except TimeoutError:record['gaps'].append('Tempo limite ao consultar o banco de teses; a ficha do tema foi preservada.')
 except (httpx.HTTPError,ValueError,KeyError,TypeError):record['gaps'].append('Identificação ou conteúdo do tema não confirmado na fonte oficial.')
 record['gaps'].append('Descrição de tema e reconhecimento da repercussão geral não são tese final de mérito. Votos e propostas de tese não são apresentados como decisão definitiva.')
 return record

async def search_subject(client,spec):
 result={'status':'official_research_unavailable','reference_date':str(spec.reference_date),'checked_at':datetime.now(timezone.utc).isoformat(),'legal_conclusion_allowed':False,'norms':[],'precedents':[],'gaps':[]}
 trace={'court':spec.court,'query':spec.subject_query,'candidates':[],'snapshots':[],'source_checks':[]}
 result['precedent_discovery']=trace
 if not spec.court or not keywords(spec.subject_query):
  result['gaps'].append('Informe o tribunal e um assunto público para pesquisar, sem dados pessoais.');return result
 if spec.reference_date!=today():result['gaps'].append('A pesquisa corrente de temas não certifica a situação do precedente na data histórica ou futura informada.');return result
 adapter=OfficialSources(client)
 if spec.court=='STF':
  for query in searches(spec.subject_query):
   try:
    html=await asyncio.wait_for(tracked(adapter,BASE+'listarProcesso.asp?'+urlencode({'txtTituloTema':query,'situacaoRG':'TODAS','ordenacao':'asc'}),trace,'html'),8)
    found=listing(html,spec.subject_query)
    if found:trace['candidates']=found;break
   except (httpx.HTTPError,ValueError,TypeError,TimeoutError):continue
 if not trace['candidates']:
  from .stf_catalog import CatalogSearch,search as catalogue_search
  catalogue=catalogue_search(CatalogSearch(query=' '.join(keywords(spec.subject_query))[:160],limit=8))
  trace['local_catalogue']={k:v for k,v in catalogue.items() if k not in ('items','notice')}
  for row in catalogue['items']:
   if spec.court!='STF' or matches(row['thesis_text'],spec.subject_query)<=0:continue
   trace['candidates'].append({'reference':Precedent(court='STF',kind='TEMA',number=row['theme']).model_dump(),'source':row['source'],'role':'local_catalogue_candidate_requires_live_verification','catalogue_bank':row['bank'],'catalogue_collected_at':catalogue['collected_at']})
 if not trace['candidates']:
  from .web_recovery import web_references
  web=await web_references(client,spec.subject_query+' '+spec.court,[]);trace['web_search']=web
  for hint in web['hints']:
   u=urlsplit(hint['url']);params=parse_qs(u.query)
   if u.scheme!='https' or u.hostname!='portal.stf.jus.br' or spec.court!='STF':continue
   n=next(iter(params.get('num') or params.get('numeroTema') or []),'')
   if not re.fullmatch(r'\d+',n):continue
   ref=Precedent(court='STF',kind='TEMA',number=int(n));trace['candidates'].append({'reference':ref.model_dump(),'source':BASE+'tema.asp?num='+n,'role':'unverified_web_lead'})
 refs=[Precedent.model_validate(r['reference']) for r in trace['candidates'][:3]]
 from .research import precedent
 records=await asyncio.gather(*(precedent(adapter,p,spec.reference_date) for p in refs))
 trace['record_checks']=[r for r in records if not r.get('official_theme')]
 result['precedents']=[r for r in records if r.get('official_theme') and matches(r['official_theme']['title']+' '+r['official_theme']['description'],spec.subject_query)>0]
 # A related theme must be explicitly named by a freshly retrieved thesis, not
 # selected from a hard-coded subject -> theme map or a model's recollection.
 if result['precedents'] and re.search(r'\b(?:teses|temas|respectivas|respectivos)\b',spec.query+' '+spec.subject_query,re.I):
  from .stf_theses import related
  seen={r['reference']['number'] for r in result['precedents']};links=[]
  for record in result['precedents'][:1]:
   for number in related(record):
    links.append((record['reference']['number'],number))
  for origin,number in links[:2]:
   if number in seen:
    next(r for r in result['precedents'] if r['reference']['number']==number)['related_by_official_thesis']=origin;continue
   try:other=await asyncio.wait_for(precedent(adapter,Precedent(court='STF',kind='TEMA',number=number),spec.reference_date),18)
   except TimeoutError:
    trace.setdefault('gaps',[]).append('Não foi possível concluir a conferência do tema relacionado '+str(number)+'.');continue
   if other.get('official_theme'):
    other['related_by_official_thesis']=origin;result['precedents'].append(other);seen.add(number)
  trace['related_theme_links']=[{'origin':origin,'theme':number,'basis':'fresh_official_thesis_reference'} for origin,number in links[:2]]
  linked=[r for r in result['precedents'] if r.get('related_by_official_thesis')]
  if linked:
   selected=[result['precedents'][0],*linked[:2]]
   trace['additional_record_checks']=[r for r in result['precedents'] if r not in selected]
   result['precedents']=selected
 if result['precedents']:result['status']='official_sources_retrieved'
 else:result['gaps'].append('Não consegui confirmar um tema pertinente neste tribunal. Refine a questão ou o regime jurídico; não é necessário conhecer previamente o número do tema.')
 return result
