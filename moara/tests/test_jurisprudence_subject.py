import unittest,json
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
import httpx
from moara.legal_mcp import jurisprudence as j
from moara.legal_mcp.contracts import today,Research,public_topic
from moara.gateway import legal_verification as gate,legal_answer

QUERY='qual o tema do stf que trata de pessoas que tem HIV tem direito a aposentadoria?'
LINK='verAndamentoProcesso.asp?incidente=100&numeroProcesso=123456&classeProcesso=RE&numeroTema=888'
HTML='<div class="tema-numero"><div>Tema:</div><a href="'+LINK+'">888</a></div><div class="tema-titulo-link"><div>Título:</div><a href="'+LINK+'">Reforma de militar portador assintomático de HIV.</a></div><div class="tema-descricao"><p>Descrição: Discute-se a incapacidade para o serviço militar.</p></div><div class="tema-leadingcase"><p><a>RE 123456</a></p></div><div class="tema-situacao-atual"><p>Acórdão de Repercussão Geral publicado</p></div>'
LIST='<table><tr><td><a href="'+LINK+'">888</a></td><td><a href="'+LINK+'">Reforma de militar portador assintomático de HIV.</a></td><td>RE 123456</td><td>Há repercussão geral</td><td></td></tr></table>'

class JurisprudenceTests(unittest.IsolatedAsyncioTestCase):
 async def test_chat_only_auto_request_uses_an_authorized_principal_profile(self):
  from moara.gateway import orchestration
  body=SimpleNamespace(model='auto',assistant_id='auto',document_ids=[],messages=[{'role':'user','content':QUERY}])
  request=SimpleNamespace(scope={},app=SimpleNamespace(state=SimpleNamespace(db=SimpleNamespace(audit=AsyncMock()))))
  actor=SimpleNamespace(can=lambda permission:permission=='chat.use')
  context=dict(id='juridica',name='Legal',version='2',revision=1,prompt_sha256='x',policy_version='2',tools=['normas.read','jurisprudencia.read'])
  identity=SimpleNamespace(resolve=lambda text:None)
  with patch.object(orchestration.assistants,'resolve',AsyncMock(return_value=context)),patch('moara.gateway.catalog_api.visible_profiles',AsyncMock(return_value=[{'id':'gemma4-12b'}])):
   selected,canonical,_=await orchestration.prepare(body,request,actor,identity,'test')
  self.assertEqual(body.model,'gemma4-12b');self.assertIsNone(canonical);self.assertTrue(selected['requires_legal_sources'])
 async def test_missing_subject_cannot_trigger_a_bulk_catalogue_download(self):
  client=SimpleNamespace(stream=AsyncMock(side_effect=AssertionError('must not fetch')))
  result=await j.search_subject(client,Research(reference_date=today(),court='STF',subject_query='tema stf'))
  self.assertEqual(result['precedents'],[]);client.stream.assert_not_called()
 def test_subject_search_uses_public_acronym_not_a_guessed_topic_number(self):
  self.assertEqual(j.searches(public_topic(QUERY))[0],'hiv')
  self.assertTrue(all(not any(c.isdigit() for c in q) for q in j.searches(public_topic(QUERY))))
 def test_official_listing_can_identify_any_topic_without_a_topic_map(self):
  candidates=j.listing(LIST,public_topic(QUERY));self.assertEqual(candidates[0]['reference']['number'],888)
  self.assertEqual(j.listing(LIST.replace(LINK,'https://evil.example/'+LINK),public_topic(QUERY)),[])
 def test_official_theme_number_must_match(self):
  self.assertEqual(j.theme_metadata(HTML,888)['leading_case'],'RE 123456')
  with self.assertRaises(ValueError):j.theme_metadata(HTML,1310)
  self.assertEqual(j.theme_metadata(HTML.replace('>888</a>','>0888</a>'),888)['number'],888)
 def test_general_repercussion_and_proposed_thesis_are_not_final_merits(self):
  meta=j.theme_metadata(HTML+'<p>Um voto propôs a tese de concessão automática.</p>',888)
  self.assertFalse(meta['final_merits_thesis_confirmed']);self.assertIn('Repercussão Geral',meta['reported_status'])
 def test_future_events_are_excluded_and_most_recent_event_is_first(self):
  html='<table><tr><td>01/01/2020</td><td>Vista</td></tr><tr><td>01/01/2099</td><td>Trânsito em julgado</td></tr><tr><td>29/10/2026</td><td>Suspenso o julgamento</td></tr></table>'
  rows=j.events(html);self.assertEqual(rows[0]['label'],'Suspenso o julgamento');self.assertEqual(len(rows),2)
 async def test_zero_results_do_not_turn_into_a_fictional_theme(self):
  with patch.object(j,'tracked',AsyncMock(return_value='<html>Sem resultados oficiais</html>')),patch('moara.legal_mcp.web_recovery.web_references',AsyncMock(return_value={'hints':[]})):
   result=await j.search_subject(SimpleNamespace(),Research(reference_date=today(),court='STF',subject_query='hiv aposentadoria'))
  self.assertEqual(result['precedents'],[]);self.assertFalse(result['legal_conclusion_allowed'])
 async def test_subject_question_routes_to_precedent_research_not_a_law_catalogue(self):
  package={'status':'official_sources_retrieved','legal_conclusion_allowed':False,'norms':[],'precedents':[]}
  http=SimpleNamespace(post=AsyncMock(return_value=httpx.Response(200,json={'result':{'structuredContent':package}},request=httpx.Request('POST','http://mcp'))))
  request=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(http=http)))
  with patch('moara.gateway.settings.secret',return_value='x'*40),patch.object(gate,'save',AsyncMock(return_value='evidence')),patch.object(legal_answer,'explain',AsyncMock(return_value={'answer':'Consulta oficial de tema','status':'official_theme_answer'})):
   await gate.preflight([{'role':'user','content':QUERY}],request,None,force=True)
  params=http.post.await_args.kwargs['json']['params'];self.assertEqual(params['name'],'research_precedents_by_subject');self.assertEqual(params['arguments']['court'],'STF');self.assertEqual(params['arguments']['norms'],[])
 async def test_military_scope_and_current_procedural_event_are_explicit_without_model_invention(self):
  meta=j.theme_metadata(HTML,888);meta.update(movements_checked=True,latest_merits_event={'date':'2026-10-29','label':'Suspenso o julgamento'})
  record={'official_theme':meta,'reference':{'court':'STF','kind':'TEMA','number':888},'source':'https://portal.stf.jus.br/theme','excerpts':[{'device':'STF TEMA 888','text':'Registro oficial do tema referente à reforma militar.','source':'https://portal.stf.jus.br/theme'}]}
  with patch('moara.gateway.chat_api.completion',AsyncMock()) as model:
   answer=await legal_answer.explain(None,None,QUERY,{'norms':[],'precedents':[record]})
  self.assertEqual(answer['status'],'official_theme_answer');self.assertIn('reforma militar',answer['answer']);self.assertIn('Suspenso o julgamento',answer['answer']);self.assertIn('INSS',answer['answer']);model.assert_not_called()
