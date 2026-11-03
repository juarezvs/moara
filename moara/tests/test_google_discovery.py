import unittest,os
from types import SimpleNamespace
from unittest.mock import patch,AsyncMock
import httpx
from pydantic import ValidationError
from moara.research_browser.policy import PublicSearch,candidate_url,robot_policy,network_permission,search_url
from moara.research_browser import google,service
from moara.legal_mcp import google_discovery,web_recovery

class GoogleDiscoveryTests(unittest.IsolatedAsyncioTestCase):
 def test_only_bounded_public_subjects_and_typed_norms_can_be_sent(self):
  for topic in ['CPF 12345678900','https://private.invalid','meu processo','senha institucional']:
   with self.assertRaises(ValidationError):PublicSearch(topic=topic)
  with self.assertRaises(ValidationError):PublicSearch(topic='licitacao',url='http://localhost')
  self.assertIn('8112/1990',PublicSearch(norms=[{'kind':'LEI','number':8112,'year':1990}]).public_query())
 def test_google_redirects_are_only_unwrapped_to_explicit_official_domains(self):
  good='https://portal.stf.jus.br/jurisprudenciaRepercussao/tema.asp?num=1310'
  self.assertEqual(candidate_url('https://www.google.com/url?q='+good),good)
  for url in ['http://portal.stf.jus.br/','https://portal.stf.jus.br.evil.invalid/','https://user@portal.stf.jus.br/','https://127.0.0.1/','file:///run/secrets/key','https://www.google.com/url?q=https://evil.invalid/']:
   self.assertIsNone(candidate_url(url))
 def test_provider_machine_readable_restrictions_cannot_be_bypassed_by_redirect(self):
  rules,proof=robot_policy(b'User-agent: *\nDisallow: /search\n')
  self.assertTrue(network_permission(search_url('hiv militar'),rules,True))
  self.assertFalse(network_permission('https://www.google.com/search?q=hiv&udm=50',rules,True))
  self.assertFalse(network_permission('http://127.0.0.1/',rules,True));self.assertIn('sha256',proof)
 def test_robot_query_delimiters_wildcards_and_longest_allow_are_preserved(self):
  rules,_=robot_policy(b'User-agent: *\nDisallow: /?\nDisallow: /search\nAllow: /search/about\nDisallow: /blocked*secret$\n')
  self.assertTrue(rules.can_fetch('Moara-SourceDiscovery','https://www.google.com/aimode?hl=pt-BR'))
  self.assertFalse(rules.can_fetch('Moara-SourceDiscovery','https://www.google.com/?q=hiv'))
  self.assertTrue(rules.can_fetch('Moara-SourceDiscovery','https://www.google.com/search/about'))
  self.assertFalse(rules.can_fetch('Moara-SourceDiscovery','https://www.google.com/blocked/path/secret'))
 async def test_a_disallowed_entry_does_not_start_a_browser(self):
  with patch.object(google,'fetch_robots',return_value=b'User-agent: *\nDisallow: /aimode\n'):
   result=await google.discover('hiv militar')
  self.assertEqual(result['status'],'provider_access_restricted');self.assertFalse(result['generated_answer_used']);self.assertEqual(result['hints'],[])
 async def test_browser_endpoint_requires_auth_rejects_arbitrary_urls_and_limits_requests(self):
  app=service.create_app('x'*40)
  with patch.object(service,'discover',AsyncMock(return_value={'status':'provider_access_restricted','hints':[]})) as discovery:
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://browser') as c:
    self.assertEqual((await c.post('/references',json={'topic':'hiv militar'})).status_code,403)
    headers={'Authorization':'Bearer '+'x'*40}
    self.assertEqual((await c.post('/references',headers=headers,json={'topic':'hiv','url':'http://localhost'})).status_code,422)
    self.assertEqual((await c.post('/references',headers={**headers,'Origin':'https://untrusted.invalid'},json={'topic':'hiv'})).status_code,403)
    self.assertEqual((await c.post('/references',headers=headers,content=b'x'*2049)).status_code,413)
    await c.post('/references',headers=headers,json={'topic':'hiv militar'})
    self.assertEqual((await c.post('/references',headers=headers,json={'topic':'hiv militar'})).json()['status'],'rate_limited')
  discovery.assert_awaited_once()
 async def test_mcp_accepts_candidate_links_but_not_google_generated_legal_evidence(self):
  payload={'status':'search_leads_retrieved','normative_evidence':False,'generated_answer_used':False,'answer':'Do not use this generated answer','hints':[{'url':'https://portal.stf.jus.br/theme','title':'Candidate'},{'url':'https://evil.invalid/','title':'Reject'}]}
  async def handler(request):return httpx.Response(200,json=payload)
  with patch.dict(os.environ,{'MOARA_REFERENCE_BROWSER_URL':'http://moara-google-browser:8077/references'}),patch.object(google_discovery,'browser_key',return_value='x'*40):
   async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:result=await google_discovery.references(c,'hiv militar',[])
  self.assertEqual(len(result['hints']),1);self.assertNotIn('answer',result);self.assertEqual(result['snapshots'],[])
 async def test_restricted_google_access_is_recorded_and_does_not_disable_existing_fallback(self):
  blocked={'provider':'google_ai_mode_browser','status':'provider_access_restricted','hints':[],'snapshots':[],'normative_evidence':False}
  fallback={'provider':'bing_public_rss','status':'no_relevant_search_leads','hints':[]}
  with patch.object(google_discovery,'references',AsyncMock(return_value=blocked)),patch.object(web_recovery,'bing_references',AsyncMock(return_value=fallback)):
   result=await web_recovery.web_references(None,'hiv militar',[])
  self.assertEqual(result['attempts'][0]['status'],'provider_access_restricted');self.assertFalse(result['attempts'][0]['normative_evidence'])
 async def test_official_domain_with_wrong_document_identity_is_not_accepted(self):
  from moara.legal_mcp.contracts import Research,Norm,today
  url='https://www2.camara.leg.br/legin/fed/lei/1990/lei-8112-11-dezembro-1990-322161-normaatualizada-pl.html'
  html='<html><body>Lei 99999 de 2025. Art. 1. Documento diferente, sem a norma pesquisada.</body></html>'
  with patch('moara.legal_mcp.catalog.tracked',AsyncMock(return_value=html)):
   records=await web_recovery.current_web_links(SimpleNamespace(),Research(reference_date=today(),norms=[Norm(kind='LEI',number=8112,year=1990)]),[{'url':url}],{'steps':[]})
  self.assertEqual(records,[])
 async def test_candidate_is_fetched_and_verified_before_becoming_official_text(self):
  from moara.legal_mcp.contracts import Research,today
  url='https://www2.camara.leg.br/legin/fed/lei/2021/lei-14133-1-abril-2021-791222-normaatualizada-pl.html';visited=[]
  body='<html><p>LEI 14.133 de 2021</p><p>Art. 32. A modalidade diálogo competitivo é restrita às contratações que envolvam inovação tecnológica ou técnica e as condições previstas neste dispositivo.</p></html>'
  async def handler(request):
   visited.append(str(request.url))
   if request.url.host=='moara-google-browser':return httpx.Response(200,json={'status':'search_leads_retrieved','normative_evidence':False,'generated_answer_used':False,'answer':'Direito automático inventado: NÃO USAR','hints':[{'url':url,'title':'Lei 14.133/2021'}]})
   self.assertEqual(str(request.url),url);return httpx.Response(200,text=body,headers={'Content-Type':'text/html; charset=utf-8'})
  with patch.dict(os.environ,{'MOARA_REFERENCE_BROWSER_URL':'http://moara-google-browser:8077/references'}),patch.object(google_discovery,'browser_key',return_value='x'*40),patch.object(web_recovery,'discover',AsyncMock(return_value={'status':'no_candidates','candidates':[],'snapshots':[]})):
   async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
    result=await web_recovery.recover(c,Research(reference_date=today(),subject_query='diálogo competitivo'))
  self.assertEqual(result['status'],'official_sources_retrieved');self.assertEqual(result['norms'][0]['source'],url)
  self.assertTrue(result['norms'][0]['snapshots']);self.assertFalse(result['legal_conclusion_allowed'])
  self.assertEqual(visited,['http://moara-google-browser:8077/references',url]);self.assertNotIn('Direito automático inventado',str(result))
