"""Topic discovery in official catalogues; every candidate remains evidence, not a verdict."""
import asyncio,re,sqlite3
from urllib.parse import urlencode,urlsplit
from .contracts import Norm,NormSearch
from .sources import OfficialSources,clean
from .catalog import tracked,search,stamp
from .texts import folded

SEARCH='https://www.camara.leg.br/legislacao/busca?'
KINDS={'lei':'LEI','leicom':'LCP','declei':'DEL','decret':'DEC','emecon':'EMC'}

def career_query(query):
 value=folded(query)
 return bool(re.search(r'\b(?:cargo|cargos|carreira|carreiras)\b',value) and re.search(r'\b(?:salario|salarios|remuneracao|vencimento|vencimentos)\b',value) and not re.search(r'\b(?:magistrados?|juizes?|ministros?)\b',value))

def query_variants(query):
 """Translate public career/pay vocabulary, retaining the requested institution.

 No statute number or ready-made answer is inferred from these terms.
 """
 if not career_query(query):
  if not re.search(r'expli|diferenc|compar|distin|como funciona',folded(query)):return [query]
  # Search for the subject, not the conversational instruction. Inflection
  # variants discover catalogue headings without mapping a topic to a law.
  drop={'explique','explicar','diferenca','diferencas','entre','compare','comparar','distincao','como','funciona','entenda','quero','saber','sobre','qual','quais','o','a','e','de','do','da','os','as'}
  words=[w for w in re.findall(r'[^\W\d_]+',query,re.UNICODE) if folded(w) not in drop]
  if re.search(r'diferenc|compar|distin',folded(query)) and len(words)>2:
   words=[w for w in words if folded(w) not in {'servidor','servidores','publico','publicos'}]
  canonical=' '.join(words)
  plural=' '.join(w[:-2]+'ões' if w.endswith('ão') else w+'s' if not w.endswith('s') else w for w in words)
  return list(dict.fromkeys(q for q in [canonical,plural,query] if len(q)>=3))[:3]
 words=re.findall(r'[^\W\d_]+',query,re.UNICODE)
 drop={'cargo','cargos','carreira','carreiras','salario','salarios','remuneracao','vencimento','vencimentos','plano','planos','de','do','da','dos','das','e','servidor','servidores'}
 remaining=[w for w in words if folded(w) not in drop]
 if any(folded(w)=='judiciario' for w in remaining):
  remaining=[{'federal':'união','uniao':'união','judiciario':'judiciário'}.get(folded(w),w) for w in remaining]
 canonical=' '.join(dict.fromkeys(['carreiras','servidores',*remaining]))
 remuneration=' '.join(dict.fromkeys(['remuneração','servidores',*remaining]))
 return list(dict.fromkeys([canonical,query,remuneration]))[:3]

def norm_link(url):
 u=urlsplit(url)
 if u.scheme!='https' or u.hostname!='www2.camara.leg.br' or u.query or u.username:return None
 m=re.fullmatch(r'/legin/fed/(lei|leicom|declei|decret|emecon)/[\d-]+/[a-z]+-(\d+)-[^/]+-(\d{4})-\d+-norma-p[le]\.html',u.path)
 if not m:return None
 try:return Norm(kind=KINDS[m[1]],number=int(m[2]),year=int(m[3]))
 except ValueError:return None

def results(html):
 rows=[]
 for part in re.findall(r'<li\b[^>]*class="busca-resultados__item[^"\n]*"[^>]*>(.*?)</li>',html,re.S):
  heading=re.search(r'<h3\b[^>]*>(.*?)</h3>',part,re.S)
  link=re.search(r'href="([^"]+)"',heading[1]) if heading else None
  if not link:continue
  url=clean(link[1]);norm=norm_link(url)
  if not norm:continue
  summary=re.search(r'<p[^>]*class="busca-resultados__descricao[^"\n]*"[^>]*>(.*?)</p>',part,re.S)
  rows.append({'norm':norm.model_dump(),'name':clean(heading[1]),'summary':re.sub(r'^Ementa:\s*','',clean(summary[1] if summary else ''))[:3000],'source':url,'catalogue_rank':len(rows)+1})
 return rows[:20]

def references(text):
 # References are search leads only; the numeric catalogue subsequently verifies them.
 for m in re.finditer(r'\b(Lei Complementar|Decreto-Lei|Lei|Decreto)\s*(?:n[º°o.s]*\s*)?(\d[\d.]*)\s*,\s*de\s+\d{1,2}[º°o]?\s+de\s+\w+\s+de\s+(\d{4})',text,re.I):
  try:yield Norm(kind={'lei':'LEI','lei complementar':'LCP','decreto-lei':'DEL','decreto':'DEC'}[m[1].casefold()],number=int(m[2].replace('.','')),year=int(m[3]))
  except ValueError:continue

def key(norm):return (norm['kind'],norm['number'],norm['year'])

def score(row,query):
 expanded=query+' '+query_variants(query)[0] if career_query(query) else query
 def tokens(text):
  stop={'diferenca','entre','compare','comparar','explique','explicar','como','funciona','qual','quais','sobre'}
  return {(t[:-3]+'ao' if t.endswith('oes') else t[:-1] if t.endswith('s') else t)[:8] for t in re.findall(r'[a-z]{4,}',folded(text)) if t not in stop}
 terms=tokens(expanded)
 words=tokens(row.get('summary','')+' '+row.get('name',''))
 summary=folded(row.get('summary',''))
 if not terms&words and not row.get('reference_hits'):return 1/(1+row.get('catalogue_rank',20))
 return 4*len(terms&words)+(7 if re.match(r'institui|cria mecanismos|dispoe sobre|estabelece|regula',summary) else 0)-(9 if re.match(r'altera|acrescenta|revoga',summary) else 0)+min(12,row.get('reference_hits',0)*2)

def record_status(html,url):
 from .texts import LegalHTML
 from urllib.parse import urljoin
 text=folded(LegalHTML(re.sub(r'>\s*<','> <',html)).text())
 revoked=bool(re.search(r'situacao:\s*revogad[ao]\b',text))
 leads=[]
 if revoked:
  for href,label in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',html,re.S|re.I):
   if re.search(r'\(revogacao\)',folded(clean(label))):
    target=urljoin(url,href);norm=norm_link(target)
    if norm:leads.append({'norm':norm.model_dump(),'source':target})
 return {'reported_revoked':revoked,'revoking_norms':leads}

async def discover(client,spec):
 result={'status':'discovery_unavailable','checked_at':stamp(),'query':spec.query,'candidates':[],'snapshots':[],'source_checks':[],'legal_conclusion_allowed':False,'coverage':'federal_partial','gaps':[]}
 adapter=OfficialSources(client)
 try:
  rows=[];result['query_variants']=query_variants(spec.query)
  from .lexml_catalog import candidates as metadata_candidates,evidence as metadata_evidence
  metadata=[]
  try:
   for query in result['query_variants']:metadata.extend(metadata_candidates(query))
   result['snapshots'].extend(metadata_evidence(metadata[:8]))
   rows.extend(metadata)
   if metadata:result['source_checks'].append({'source':'LexML/Senado local metadata catalogue','status':'cached_discovery_only','checked_at':stamp(),'freshly_rechecked':False,'catalogue_versions':list({r['catalogue_version'] for r in metadata})})
  except (OSError,ValueError,sqlite3.Error):
   result['gaps'].append('Catálogo local de metadados indisponível; a busca oficial continua.')
  for query in result['query_variants']:
   try:
    html=await tracked(adapter,SEARCH+urlencode({'geral':query}),result,'html')
    rows.extend({**row,'discovered_by_query':query} for row in results(html))
   except Exception as error:
    import httpx
    if not isinstance(error,(httpx.HTTPError,ValueError)):raise
    continue
  pool={}
  for row in rows:
   k=key(row['norm'])
   if k not in pool:pool[k]={**row,'reference_hits':0}
  rows=list(pool.values())
  leads={}
  for row in rows:
   for n in references(row['summary']):
    k=key(n.model_dump());leads[k]=leads.get(k,0)+1
  # Recurring references often identify the underlying code rather than an amending act.
  for k,count in sorted(leads.items(),key=lambda item:-item[1])[:3]:
   if k in pool:pool[k]['reference_hits']=count;continue
   found=await search(client,NormSearch(kind=k[0],number=k[1],year=k[2]))
   result['snapshots'].extend(found['snapshots']);result['source_checks'].extend(found['source_checks'])
   if len(found['candidates'])!=1:continue
   hit=found['candidates'][0]
   pool[k]={'norm':Norm(kind=k[0],number=k[1],year=k[2]).model_dump(),'name':hit['name'],'summary':hit['summary'],'source':hit['source'],'reference_hits':count}
  ranked=sorted(pool.values(),key=lambda r:-score(r,spec.query))
  # Catalogue matches are not necessarily active norms. An explicit official
  # total-revocation label excludes a candidate from current subject answers;
  # the linked revoking act is a lead, not an assumed replacement rule.
  for row in ranked[:4]:
   if not norm_link(row.get('source','')):continue
   try:
    page=await tracked(adapter,row['source'],result,'html')
    state=record_status(page,row['source']);row.update(state)
    for lead in state['revoking_norms']:
     if key(lead['norm']) in pool:pool[key(lead['norm'])]['official_revocation_lead']=True
   except Exception as error:
    import httpx
    if not isinstance(error,(httpx.HTTPError,ValueError)):raise
  ranked=sorted(pool.values(),key=lambda r:-(score(r,spec.query)+(12 if r.get('official_revocation_lead') else 0)))
  ranked=[r for r in ranked if not r.get('reported_revoked')]
  result['candidates']=[{**r,'relevance_score':score(r,spec.query)} for r in ranked if score(r,spec.query)>0][:8]
  result['status']='official_candidates_retrieved' if result['candidates'] else 'no_relevant_official_candidates'
 except (ValueError,KeyError,TypeError) as e:result['gaps'].append('Não foi possível interpretar o catálogo oficial nesta consulta.')
 except Exception as e:
  import httpx
  if not isinstance(e,httpx.HTTPError):raise
  result['gaps'].append('O catálogo oficial não respondeu nesta consulta.')
 result['gaps'].append('Busca federal por assunto com cobertura parcial. Relevância no catálogo não confirma vigência, exclusividade ou aplicação ao caso.')
 return result

async def current_camara(adapter,spec,at,result):
 """Discover the current-text link from the exact official catalogue record."""
 from .contracts import today
 from .texts import articles_from_html,LegalHTML
 if at!=today():return []
 html=await tracked(adapter,SEARCH+urlencode({'geral':f'{spec.number:,}'.replace(',','.'),'ano':spec.year}),result,'html')
 matching=[r for r in results(html) if key(r['norm'])==(spec.kind,spec.number,spec.year)]
 if len(matching)!=1:raise ValueError('ambiguous_camara_norm')
 record=await tracked(adapter,matching[0]['source'],result,'html')
 state=record_status(record,matching[0]['source']);result['catalogue_status']=state
 if state['reported_revoked']:
  result['gaps'].append('O catálogo oficial informa revogação total desta norma; seu texto não será usado como regra atual.')
  return []
 urls=list(dict.fromkeys(re.findall(r'href=["\']([^"\']+normaatualizada[^"\']+\.html)["\']',record,re.I)))
 from urllib.parse import urljoin
 for raw in urls[:2]:
  url=urljoin(matching[0]['source'],raw);u=urlsplit(url)
  # Only the identified norm's own current-text page, never a similarly named amendment.
  prefix=matching[0]['source'].rsplit('-norma-',1)[0]+'-normaatualizada-'
  if u.hostname!='www2.camara.leg.br' or not url.startswith(prefix):continue
  body=await tracked(adapter,url,result,'html');head=LegalHTML(body).text()[:6000]
  if str(spec.number) not in re.sub(r'(?<=\d)\.(?=\d)','',head) or str(spec.year) not in head:continue
  excerpts=articles_from_html(body,url,spec.articles,at)
  result.update(source=url,text_selection_basis='official_current_compilation_retrieved_now',status='official_text_retrieved',name=matching[0]['name'],summary=matching[0]['summary'],identity_source=matching[0]['source'])
  result['gaps'].append('Texto atualizado vinculado pelo catálogo da Câmara, conferido agora; não é comprovação de redação histórica.')
  return excerpts
 return []
