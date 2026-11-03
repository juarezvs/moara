import unittest,json,uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch,AsyncMock
import httpx
from moara.legal_mcp import texts,sources,research
from moara.legal_mcp.contracts import today,Norm,Research,identify_precedents
from moara.gateway import legal_answer

HTML='<html><p>Art. 8º São formas de provimento de cargo público:</p><p>I - nomeação;</p><p>II - promoção;</p><p><s>III - transferência antiga;</s></p><p>Art. 10. Os demais requisitos para o desenvolvimento na carreira mediante promoção dependem da lei e seus regulamentos.</p><p>Art. 17. A promoção não interrompe o tempo de exercício.</p></html>'

class LegalTextTests(unittest.TestCase):
 def test_jsonld_mixed_arrays_cannot_crash_source_reader(self):
  self.assertEqual(sources.sequence(['reference',None,{'x':1}]),[{'x':1}]);self.assertEqual(sources.mapping(''),{})
 def test_current_html_excludes_struck_text_and_does_not_claim_amendment_date(self):
  ex=texts.articles_from_html(HTML,'https://normas.leg.br/test',[],today())
  self.assertEqual([e['device'] for e in ex],['art8','art10','art17']);self.assertNotIn('antiga',ex[0]['text'])
  self.assertFalse(ex[0]['effective_date_confirmed']);self.assertEqual(ex[0]['version_date_basis'],'retrieval_date_not_amendment_or_effective_date')
 def test_current_compilation_cannot_be_used_for_historical_date(self):
  with self.assertRaises(ValueError):texts.articles_from_html(HTML,'https://normas.leg.br/test',[],today()-timedelta(days=1))
 def test_retrieval_ranks_relevant_articles_after_first_hundred(self):
  ex=[{'device':'art'+str(i),'text':'Texto irrelevante.'} for i in range(300)]+[{'device':'art301','text':'A promoção não interrompe o tempo de exercício.'}]
  self.assertEqual(texts.relevant(ex,'o que é promoção?')[0]['device'],'art301')
 def test_court_is_required_and_same_topic_number_is_not_confused(self):
  self.assertEqual(identify_precedents('Explique Tema 1157'),[])
  refs=identify_precedents('Tema 1157 do STJ e Tema 1157 do STF')
  self.assertEqual([(p.court,p.kind,p.number) for p in refs],[('STJ','TEMA',1157),('STF','TEMA',1157)])

class GroundingTests(unittest.TestCase):
 def rows(self):return [{'id':'L1.1','device':'art17','text':'Art. 17. A promoção não interrompe o tempo de exercício.','norm':{'kind':'LEI','number':8112,'year':1990},'source':'https://normas.leg.br/'}]
 def test_claim_requires_existing_source_and_literal_supporting_quote(self):
  value={'points':[{'text':'A promoção preserva a continuidade do exercício.','source_id':'L1.1','quote':'A promoção não interrompe o tempo de exercício.'}]}
  self.assertEqual(len(legal_answer.validate(value,self.rows())),1)
  for key,text in [('source_id','L99.1'),('quote','Você tem direito à promoção em dois anos.'),('text','A Lei 9999/2000 garante a promoção.'),('text','O art. 99 garante a promoção.')]:
   bad=json.loads(json.dumps(value));bad['points'][0][key]=text
   with self.assertRaises(ValueError):legal_answer.validate(bad,self.rows())
 def test_client_json_cannot_construct_private_research_capability(self):
  self.assertIsNot(True,legal_answer.RESEARCH_CAPABILITY);self.assertIsNot({'enabled':True},legal_answer.RESEARCH_CAPABILITY)

class ResearchFailureTests(unittest.IsolatedAsyncioTestCase):
 async def test_8112_current_encoding_404_falls_back_to_live_camara_compilation(self):
  urn='urn:lex:br:federal:lei:1990-12-11;8112'
  metadata={'DetalheDocumento':{'documentos':{'documento':{'identificacao':{'urlDocumento':'https://normas.leg.br/?urn='+urn,'numero':'8112','tipo':'LEI','dataassinatura':'11/12/1990'},'disps':'','vides':''}}}}
  broken='https://normas.leg.br/api/binario/228b2aee-5078-4b66-952f-2dd5fc41909b/texto'
  structured={'legislationIdentifier':urn,'encoding':[{'version':'Current','contentUrl':broken,'encodesCreativeWork':{'@id':'https://normas.leg.br/?urn='+urn+'@versao.atualizada~texto;pt'}}]}
  async def fetch(url,expected='json'):
   if url==broken:raise httpx.HTTPStatusError('404',request=httpx.Request('GET',url),response=httpx.Response(404))
   data=metadata if '/dadosabertos/' in url else structured if '/api/public/' in url else '<h1>LEI Nº 8.112 DE 1990</h1>'+HTML
   return data,{'url':url,'sha256':'test','retrieved_at':str(today())}
  adapter=sources.OfficialSources(SimpleNamespace())
  with patch.object(adapter,'fetch',AsyncMock(side_effect=fetch)):
   value=await adapter.norm(Norm(kind='LEI',number=8112,year=1990),today(),enrich=False)
  self.assertEqual(value['status'],'official_text_retrieved');self.assertIn('www2.camara.leg.br',value['source'])
  self.assertEqual([e['device'] for e in value['excerpts']],['art8','art10','art17'])
  self.assertTrue(any(c.get('http_status')==404 for c in value['source_checks']))
 async def test_unavailable_reference_does_not_erase_other_sources(self):
  async def norm(adapter,n,at,enrich=True):
   if n.number==8112:raise AttributeError('unexpected external shape')
   return {'norm':n.model_dump(),'excerpts':[{'device':'art6','text':'Texto oficial conceitual.'}],'snapshots':[]}
  with patch.object(sources.OfficialSources,'norm',norm):
   package=await research.research(SimpleNamespace(),Research(reference_date=today(),norms=[Norm(kind='LEI',number=8112,year=1990),Norm(kind='LEI',number=14133,year=2021)],query='conceitual'))
  self.assertEqual(package['status'],'official_sources_retrieved');self.assertEqual(package['norms'][0]['excerpts'],[])
  self.assertTrue(package['norms'][1]['excerpts']);self.assertFalse(package['legal_conclusion_allowed'])
 async def test_model_failure_preserves_real_source_excerpt(self):
  from moara.gateway import chat_api
  package={'norms':[{'norm':{'kind':'LEI','number':8112,'year':1990},'source':'https://normas.leg.br/',
      'excerpts':[{'device':'art17','text':'A promoção não interrompe o tempo de exercício.'}]}]}
  with patch.object(chat_api,'completion',AsyncMock(side_effect=ValueError('model response invalid'))):
   value=await legal_answer.explain(None,None,'o que é promoção?',package)
  self.assertEqual(value['status'],'quoted_sources_fallback');self.assertIn('não interrompe',value['answer'])
 async def test_unapproved_document_cannot_trigger_private_network_access(self):
  client=SimpleNamespace(stream=AsyncMock(side_effect=AssertionError('must not request')))
  value=await research.research(client,Research(reference_date=today(),official_urls=['https://127.0.0.1/secrets']))
  self.assertFalse(value['norms'][0]['excerpts']);client.stream.assert_not_called()
