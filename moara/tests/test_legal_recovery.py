import unittest,json
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from datetime import timedelta
import httpx
from moara.legal_mcp import web_recovery as web,discovery
from moara.legal_mcp.contracts import Norm,Research,today
from moara.gateway import legal_verification as gate

N=Norm(kind='LEI',number=14133,year=2021)
URL='https://www2.camara.leg.br/legin/fed/lei/2021/lei-14133-1-abril-2021-791222-normaatualizada-pl.html'
BODY='<html><p>LEI 14.133 de 2021</p><p>Art. 32. A modalidade diálogo competitivo é restrita às contratações que envolvam inovação tecnológica ou técnica e as condições previstas neste dispositivo.</p></html>'

class RecoveryTests(unittest.IsolatedAsyncioTestCase):
 async def test_recovered_conditions_preserve_literal_conjunctions(self):
  from moara.gateway.legal_answer import explain
  package={'recovery':{'status':'official_text_recovered','steps':[{'topic':'diálogo competitivo'}]},'norms':[{'norm':N.model_dump(),'excerpts':[{'device':'art32_cpt','text':'A modalidade diálogo competitivo é restrita às seguintes condições.','source':URL},{'device':'art32_cpt_inc1','text':'Inovação tecnológica e impossibilidade de definição prévia.','source':URL}]}]}
  with patch('moara.gateway.chat_api.completion',AsyncMock()) as model:
   answer=await explain(None,None,'Liste os critérios do diálogo competitivo',package)
  self.assertEqual(answer['status'],'official_conditions_answer');self.assertIn('tecnológica e impossibilidade',answer['answer']);model.assert_not_called()
 def test_matched_caput_keeps_conditions_even_without_repeating_topic_words(self):
  from moara.legal_mcp.texts import relevant
  excerpts=[{'device':'art32_cpt','text':'A modalidade diálogo competitivo é restrita às contratações em que a Administração:'},{'device':'art32_cpt_inc1','text':'vise a contratar objeto que envolva inovação tecnológica ou técnica;'},{'device':'art99_cpt','text':'Uma disposição sem relação com o assunto.'}]
  selected=relevant(excerpts,'diálogo competitivo')
  self.assertEqual([e['device'] for e in selected],['art32_cpt','art32_cpt_inc1'])
 def test_informational_procurement_question_routes_to_legal_chat_without_document_grant(self):
  from moara.gateway.orchestration import contextual_rules
  result=contextual_rules('me explique como funciona e os critérios para usar a modalidade diálogo competitivo.')
  self.assertEqual(result['assistant'],'juridica');self.assertTrue(result['requires_legal_sources'])
 def test_unrelated_search_results_are_rejected(self):
  self.assertFalse(web.relevant_hint('WhatsApp Web','Mensagens e chamadas','diálogo competitivo'))
  self.assertTrue(web.relevant_hint('Diálogo competitivo','Lei de licitações e suas regras','diálogo competitivo'))
  self.assertFalse(web.has_topic_text({'norms':[{'excerpts':[{'device':'art1','text':'Institui o Programa Mais Alimentos para apoiar as atividades agropecuárias brasileiras.'}]}]},'diálogo competitivo'))
 async def test_model_reformulation_cannot_add_private_terms_or_invent_law_numbers(self):
  value={'choices':[{'message':{'content':'{"topics":["Lei 99999/2030"]}'}}]}
  with patch('moara.gateway.chat_api.completion',AsyncMock(return_value=value)):
   topics=await gate.recovery_topics(None,object(),'me explique como funciona e os critérios para usar a modalidade diálogo competitivo.')
  self.assertNotIn('99999',' '.join(topics));self.assertIn('competitivo',' '.join(topics))
 async def test_reformulation_selects_only_existing_public_words(self):
  value={'choices':[{'message':{'content':json.dumps({'topics':['diálogo competitivo']})}}]}
  with patch('moara.gateway.chat_api.completion',AsyncMock(return_value=value)):
   self.assertEqual(await gate.recovery_topics(None,object(),'me explique como funciona e os critérios para usar a modalidade diálogo competitivo.'),['diálogo competitivo'])
 async def test_focused_catalogue_recovery_uses_official_text(self):
  found={'status':'official_candidates_retrieved','snapshots':[],'candidates':[{'norm':N.model_dump()}]}
  package={'status':'official_sources_retrieved','legal_conclusion_allowed':False,'norms':[{'norm':N.model_dump(),'excerpts':[{'device':'art32','text':'A modalidade diálogo competitivo é restrita às condições estabelecidas na lei oficial.'}]}]}
  with patch.object(web,'discover',AsyncMock(return_value=found)),patch('moara.legal_mcp.research.research',AsyncMock(return_value=package)),patch.object(web,'web_references',AsyncMock()) as search:
   result=await web.recover(SimpleNamespace(),Research(reference_date=today(),subject_query='diálogo competitivo',recovery_topics=['diálogo competitivo']))
  self.assertEqual(result['recovery']['status'],'official_text_recovered');search.assert_not_called()
 async def test_search_snippet_alone_cannot_ground_a_legal_answer(self):
  hint={'title':'Lei 14133/2021 — diálogo competitivo','description':'Texto não conferido de um blog.','url':'https://example.org/blog'}
  with patch.object(web,'discover',AsyncMock(return_value={'status':'unavailable','snapshots':[],'candidates':[]})),patch.object(web,'web_references',AsyncMock(return_value={'hints':[hint]})),patch('moara.legal_mcp.research.research',AsyncMock(return_value={'norms':[]})):
   result=await web.recover(SimpleNamespace(),Research(reference_date=today(),subject_query='diálogo competitivo'))
  self.assertFalse(web.has_text(result));self.assertEqual(result['norms'],[]);self.assertFalse(result['recovery']['untrusted_text_used_as_law'])
 async def test_web_lead_can_recover_current_text_only_from_its_official_url(self):
  hint={'title':'Lei 14.133/2021','description':'Diálogo competitivo','url':URL}
  async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,text=BODY))) as client:
   records=await web.current_web_links(client,Research(reference_date=today(),norms=[N],subject_query='diálogo competitivo'),[hint],{'steps':[]})
  self.assertEqual(records[0]['excerpts'][0]['device'],'art32');self.assertEqual(records[0]['source'],URL)
  self.assertFalse(records[0]['excerpts'][0]['effective_date_confirmed'])
 async def test_historical_request_cannot_use_current_web_copy(self):
  http=SimpleNamespace(stream=AsyncMock(side_effect=AssertionError('no current fetch')))
  records=await web.current_web_links(http,Research(reference_date=today()-timedelta(days=1)),[{'url':URL}],{'steps':[]})
  self.assertEqual(records,[]);http.stream.assert_not_called()
 async def test_private_urls_and_other_norms_are_not_fetched(self):
  http=SimpleNamespace(stream=AsyncMock(side_effect=AssertionError('not allowed')))
  records=await web.current_web_links(http,Research(reference_date=today(),norms=[Norm(kind='LEI',number=8112,year=1990)]),[{'url':'https://127.0.0.1/secrets'},{'url':URL}],{'steps':[]})
  self.assertEqual(records,[]);http.stream.assert_not_called()
 def test_generic_catalogue_verbs_do_not_rank_unrelated_laws_above_matching_references(self):
  unrelated=discovery.score({'summary':'Institui o Programa Mais Alimentos.','name':'Lei exemplo'},'diálogo competitivo')
  self.assertGreater(discovery.score({'summary':'Lei de Licitações e Contratos Administrativos.','reference_hits':1},'diálogo competitivo'),unrelated)
 def test_ordinal_publication_day_does_not_hide_the_underlying_law(self):
  self.assertEqual(list(discovery.references('Lei nº 14.133, de 1º de abril de 2021')),[N])

class ApplicationRecoveryTests(unittest.IsolatedAsyncioTestCase):
 async def test_empty_primary_result_must_attempt_mcp_recovery_before_answering(self):
  responses=[{'status':'official_research_unavailable','legal_conclusion_allowed':False,'norms':[]},{'status':'official_sources_retrieved','legal_conclusion_allowed':False,'norms':[{'norm':N.model_dump(),'excerpts':[{'device':'art32','text':'Dispositivo oficial recuperado para explicar os critérios do diálogo competitivo.'}]}],'recovery':{'attempted':True,'status':'official_text_recovered'}}]
  http=SimpleNamespace(post=AsyncMock(side_effect=[httpx.Response(200,json={'result':{'structuredContent':p}},request=httpx.Request('POST','http://mcp')) for p in responses]))
  request=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(http=http)))
  with patch('moara.gateway.settings.secret',return_value='x'*40),patch.object(gate,'save',AsyncMock(return_value='evidence')),patch('moara.gateway.legal_answer.explain',AsyncMock(return_value={'answer':'Explicação com fonte oficial','status':'grounded_explanation'})):
   result=await gate.preflight([{'role':'user','content':'Explique a Lei 14133/2021.'}],request,None,force=True)
  self.assertEqual([c.kwargs['json']['params']['name'] for c in http.post.await_args_list],['research_legal_sources','recover_legal_sources'])
  self.assertIn('Explicação',result['answer'])
