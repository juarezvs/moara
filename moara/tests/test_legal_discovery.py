import unittest,json
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from datetime import timedelta
import httpx
from pydantic import ValidationError
from moara.legal_mcp import discovery,research,texts
from moara.legal_mcp.contracts import SubjectSearch,Research,Norm,today,public_topic
from moara.gateway import legal_verification as gate

CTB='https://www2.camara.leg.br/legin/fed/lei/1997/lei-9503-23-setembro-1997-372348-norma-pl.html'
def row(number,year,summary):
 return '<li class="busca-resultados__item "><h3><a href="https://www2.camara.leg.br/legin/fed/lei/'+str(year)+'/lei-'+str(number)+'-1-janeiro-'+str(year)+'-1234-norma-pl.html">Lei '+str(number)+'</a></h3><p class="busca-resultados__descricao">Ementa: '+summary+'</p></li>'

class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
 def test_original_question_is_a_topic_without_requiring_law_number(self):
  self.assertEqual(public_topic('qual a lei que trata de crime de trânsitos?'),'crimes trânsito')
  self.assertTrue(gate.informational_query('crimes de trânsito'))
 def test_identifiers_and_private_case_narratives_are_not_external_topics(self):
  for q in ['Meu processo 123456 trata de crime de trânsito','Qual lei protege meu CPF 12345678901?','Qual a lei aplicável ao anexo?','Qual norma protege pessoa@example.org?']:
   self.assertEqual(public_topic(q),'')
  for q in ['crime 12345','https://127.0.0.1','muitos '+('termos '*15)]:
   with self.assertRaises(ValidationError):SubjectSearch(query=q)
 def test_only_identified_federal_metadata_links_are_candidates(self):
  self.assertEqual(discovery.norm_link(CTB),Norm(kind='LEI',number=9503,year=1997))
  for u in [CTB.replace('www2.camara.leg.br','example.org'),CTB.replace('/fed/','/est/'),CTB.replace('-norma-','-publicacaooriginal-'),CTB+'?redirect=http://127.0.0.1']:
   self.assertIsNone(discovery.norm_link(u))
 async def test_underlying_code_is_discovered_from_official_amendment_references(self):
  html=row(13546,2017,'Altera a Lei nº 9.503, de 23 de setembro de 1997 (Código de Trânsito Brasileiro), para dispor sobre crimes cometidos na direção de veículos automotores.')
  found={'candidates':[{'name':'Lei 9.503/1997','summary':'Institui o Código de Trânsito Brasileiro.','source':'https://legis.senado.leg.br/norma'}],'snapshots':[],'source_checks':[]}
  with patch.object(discovery,'tracked',AsyncMock(return_value=html)),patch.object(discovery,'search',AsyncMock(return_value=found)) as numeric:
   result=await discovery.discover(SimpleNamespace(),SubjectSearch(query='crimes trânsito'))
  self.assertEqual(result['candidates'][0]['norm']['number'],9503);numeric.assert_awaited_once();self.assertFalse(result['legal_conclusion_allowed'])
 async def test_unverified_reference_is_not_promoted_to_a_norm_identity(self):
  html=row(13546,2017,'Altera a Lei nº 9.503, de 23 de setembro de 1997 sobre crimes de trânsito.')
  with patch.object(discovery,'tracked',AsyncMock(return_value=html)),patch.object(discovery,'search',AsyncMock(return_value={'candidates':[],'snapshots':[],'source_checks':[]})):
   result=await discovery.discover(SimpleNamespace(),SubjectSearch(query='crimes trânsito'))
  self.assertFalse(any(r['norm']['number']==9503 for r in result['candidates']))
 async def test_current_text_must_be_linked_to_the_exact_norm(self):
  html=row(9503,1997,'Institui o Código de Trânsito Brasileiro.').replace('https://www2.camara.leg.br/legin/fed/lei/1997/lei-9503-1-janeiro-1997-1234-norma-pl.html',CTB)
  current=CTB.replace('-norma-','-normaatualizada-')
  record='<html><a href="'+current+'">Texto Atualizado</a></html>'
  body='<html><p>Lei 9.503 de 1997</p><p>Art. 291. Aos crimes cometidos na direção de veículos automotores aplicam-se as normas gerais.</p></html>'
  with patch.object(discovery,'tracked',AsyncMock(side_effect=[html,record,body])):
   result={'gaps':[]};ex=await discovery.current_camara(None,Norm(kind='LEI',number=9503,year=1997),today(),result)
  self.assertEqual(ex[0]['device'],'art291');self.assertEqual(result['source'],current)
  with patch.object(discovery,'tracked',AsyncMock()) as fetch:
   self.assertEqual(await discovery.current_camara(None,Norm(kind='LEI',number=9503,year=1997),today()-timedelta(days=1),{}),[]);fetch.assert_not_called()
 async def test_no_results_do_not_invent_a_law(self):
  with patch.object(discovery,'tracked',AsyncMock(return_value='<html>Sem resultados</html>')):
   result=await discovery.discover(SimpleNamespace(),SubjectSearch(query='assunto inexistente'))
  self.assertEqual(result['candidates'],[]);self.assertEqual(result['status'],'no_relevant_official_candidates')

class TopicPreflightTests(unittest.IsolatedAsyncioTestCase):
 async def test_model_cannot_invent_candidate_ids(self):
  candidate={'norm':Norm(kind='LEI',number=9503,year=1997).model_dump(),'name':'CTB','summary':'Institui o Código de Trânsito Brasileiro.'}
  output={'choices':[{'message':{'content':'{"selected_ids":[999]}'}}]}
  with patch('moara.gateway.chat_api.completion',AsyncMock(return_value=output)):
   selection=await gate.rank_subject_candidates(None,object(),'crimes trânsito',{'candidates':[candidate]})
  self.assertEqual(selection['selected_ids'],[1]);self.assertEqual(selection['status'],'catalogue_ranking')
 async def test_identity_answer_is_built_from_retrieved_metadata(self):
  from moara.gateway.legal_answer import explain
  package={'discovery':{'selection':{'inference_used':True}},'norms':[{'norm':Norm(kind='LEI',number=12345,year=2010).model_dump(),'excerpts':[{'device':'identificacao','text':'Lei 12345/2010 — Institui o assunto sintético de teste.','source':'https://legis.senado.leg.br/exemplo'}]}]}
  result=await explain(None,None,'Qual lei trata desse assunto?',package)
  self.assertIn('12345/2010',result['answer']);self.assertNotIn('9503',result['answer']);self.assertEqual(result['status'],'official_identity_answer')
 async def call(self,messages):
  package={'status':'official_sources_retrieved','legal_conclusion_allowed':False,'norms':[{'norm':Norm(kind='LEI',number=9503,year=1997).model_dump(),'excerpts':[{'device':'art1','text':'Fonte sint?tica suficiente para validar o encaminhamento desta consulta e preservar seu contexto.'}]}],'checked_at':'test'}
  candidate={'norm':Norm(kind='LEI',number=9503,year=1997).model_dump(),'name':'CTB','summary':'Institui o CTB','source':CTB}
  discovery_package={'legal_conclusion_allowed':False,'candidates':[candidate]}
  def response(**kwargs):return httpx.Response(200,json={'result':{'structuredContent':kwargs}},request=httpx.Request('POST','http://mcp'))
  http=SimpleNamespace(post=AsyncMock(side_effect=[response(**discovery_package),response(**package)]))
  request=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(http=http)))
  with patch('moara.gateway.settings.secret',return_value='x'*40),patch.object(gate,'save',AsyncMock(return_value='evidence')),patch('moara.gateway.legal_answer.explain',AsyncMock(return_value={'answer':'Resposta sintética fundamentada','status':'grounded_explanation'})):
   answer=await gate.preflight(messages,request,None,force=True)
  return answer,http
 async def test_exact_question_calls_mcp_topic_research_with_current_date(self):
  answer,http=await self.call([{'role':'user','content':'qual a lei que trata de crime de trânsitos?'}])
  rpc=http.post.await_args.kwargs['json']['params'];self.assertEqual(rpc['name'],'research_legal_sources');self.assertEqual(rpc['arguments']['subject_query'],'crimes trânsito');self.assertEqual(rpc['arguments']['reference_date'],str(today()))
  self.assertNotEqual(answer['legal_verification']['status'],'clarification_required')
 async def test_new_topic_does_not_inherit_old_law_or_case_date(self):
  answer,http=await self.call([{'role':'user','content':'Lei 8112/1990, data de referência: 15/06/2020'},{'role':'user','content':'qual a lei que trata de crime de trânsitos?'}])
  args=http.post.await_args.kwargs['json']['params']['arguments'];self.assertEqual([n['number'] for n in args['norms']],[9503]);self.assertEqual(args['reference_date'],str(today()));self.assertEqual(args['subject_query'],'crimes trânsito')
 async def test_historical_discovery_cannot_select_a_law_not_yet_published(self):
  answer,http=await self.call([{'role':'user','content':'Qual lei trata de crimes de trânsito, data de referência: 15/06/1990?'}])
  args=http.post.await_args.kwargs['json']['params']['arguments'];self.assertEqual(args['norms'],[]);self.assertEqual(args['reference_date'],'1990-06-15')
 async def test_concrete_case_still_requests_necessary_date_without_external_discovery(self):
  result=await gate.preflight([{'role':'user','content':'Qual lei se aplica ao meu caso de trânsito ocorrido antigamente?'}],None,None,force=True)
  self.assertEqual(result['legal_verification']['status'],'clarification_required')
