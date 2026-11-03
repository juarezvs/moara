"""Google browser output supplies candidate URLs, never authoritative content."""
import os
from pathlib import Path
import httpx
from moara.research_browser.policy import PublicSearch,candidate_url

def browser_key():return Path(os.getenv('MOARA_BROWSER_KEY_FILE','/run/secrets/moara_google_browser_key')).read_text().strip()

async def references(client,topic,norms):
 result={'provider':'google_ai_mode_browser','status':'not_configured','hints':[],'snapshots':[],'normative_evidence':False,'generated_answer_used':False,'gaps':[]}
 url=os.getenv('MOARA_REFERENCE_BROWSER_URL','')
 if not url:return result
 # This endpoint is deployment configuration, never a model/user-provided URL.
 if url!='http://moara-google-browser:8077/references':result['status']='invalid_provider_configuration';return result
 try:
  spec=PublicSearch(topic=topic,norms=[{k:getattr(n,k) for k in ('kind','number','year')} for n in norms[:2]])
  response=await client.post(url,headers={'Authorization':'Bearer '+browser_key()},json=spec.model_dump(),timeout=38)
  response.raise_for_status();data=response.json()
  if not isinstance(data,dict) or data.get('normative_evidence') is not False or data.get('generated_answer_used') is not False:raise ValueError('untrusted_provider_response')
  result.update(status=str(data.get('status','search_unavailable'))[:80],robots=data.get('robots'),navigation_checks=data.get('navigation_checks',[])[:5],checked_at=data.get('checked_at'),gaps=[str(g)[:400] for g in data.get('gaps',[])[:4]])
  for key in ('failure_stage','failure_kind'):
   if data.get(key):result[key]=str(data[key])[:80]
  if result['status']=='search_leads_retrieved':
   for hint in data.get('hints',[])[:8]:
    if not isinstance(hint,dict):continue
    source=candidate_url(str(hint.get('url','')))
    if source:result['hints'].append({'url':source,'title':str(hint.get('title',''))[:500],'description':'','role':'unverified_search_lead'})
 except (OSError,httpx.HTTPError,ValueError,TypeError,KeyError):
  result.update(status='search_unavailable',hints=[],gaps=['Pesquisa no Google indisponível ou entrada não pública; nenhuma resposta do provedor foi usada como evidência.'])
 return result
