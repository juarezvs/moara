import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
import httpx
from moara.gateway import legal_drafting as draft,legal_verification as legal,legal_answer
from moara.legal_mcp.contracts import today

QUESTION='crie uma petição para aposentadoria de um pescador, segurado especial, com fundamentação jurídica robusta.'

class DraftIntentTests(unittest.TestCase):
 def test_portal_instructions_do_not_destroy_public_subject(self):
  query=QUESTION+'\n\n'+draft.PORTAL_DRAFT
  self.assertTrue(draft.requested(query));self.assertTrue(draft.special_fisher(query))
  self.assertEqual(draft.subject(query),'aposentadoria pescador segurado especial')
  self.assertNotIn('hipóteses',draft.subject(query))
 def test_current_information_and_case_question_are_not_drafts(self):
  for query in ['Explique a aposentadoria do pescador segurado especial.','Posso me aposentar no meu caso?','Quais são os requisitos da petição inicial?']:
   self.assertFalse(draft.requested(query))
 def test_private_details_are_not_public_search_terms(self):
  query='Crie uma petição para minha aposentadoria como pescador segurado especial, CPF 123.456.789-00. Meu nome é Pessoa Fictícia.'
  self.assertEqual(draft.subject(query),'aposentadoria pescador segurado especial')
 def test_source_leads_are_norm_identifiers_and_not_precomputed_rules(self):
  lead=draft.research_leads(QUESTION)[0]
  self.assertEqual((lead.number,lead.year),(8213,1991));self.assertIn('11',lead.articles)
  self.assertEqual(draft.research_leads('Elabore uma petição de alimentos.'),[])
 def test_actual_petition_has_facts_grounds_requests_and_fields(self):
  text=draft.render(QUESTION,{'answer':'Fundamento recuperado [L1.1](https://www2.camara.leg.br/fonte)'},{})
  for expected in ['PETIÇÃO INICIAL','em face do INSS','Dos fatos','fundamentação jurídica','Dos pedidos','[DER','Hipótese','Fundamento recuperado']:
   self.assertIn(expected,text)
  self.assertNotIn('tem direito à aposentadoria',text)
 def test_outage_still_returns_document_without_invented_grounds(self):
  text=draft.render(QUESTION,{},{});self.assertIn('Dos pedidos',text);self.assertIn('FUNDAMENTAÇÃO PENDENTE',text)
  self.assertNotIn('art. 48',text.casefold());self.assertNotIn('Tema ',text)
 def test_administrative_request_does_not_become_judicial_action(self):
  text=draft.render('Elabore requerimento administrativo de aposentadoria de pescador segurado especial.',{},{})
  self.assertIn('REQUERIMENTO ADMINISTRATIVO',text);self.assertIn('perante o INSS',text);self.assertNotIn('em face do INSS',text)
 def test_draft_schema_keeps_finite_evidence_ids(self):
  fmt=legal_answer.explanation_format({'L1.1:1':{}},maximum=6)['json_schema']['schema']['properties']['paragraphs']
  self.assertEqual(fmt['maxItems'],6);self.assertEqual(fmt['items']['properties']['support_ids']['items']['enum'],['L1.1:1'])
 def test_inline_wrapped_cross_reference_does_not_truncate_actual_article(self):
  from moara.legal_mcp.texts import articles_from_html
  html='<p>Art. 11. Pessoas seguradas:</p><p>VII - condição nos termos do<br>art. 2º da Lei de referência;</p><p>b) pescador artesanal e condições.</p><p>Art. 12. Outro dispositivo.</p>'
  rows=articles_from_html(html,'https://www2.camara.leg.br/fonte',['11'],today())
  self.assertIn('pescador artesanal',rows[0]['text']);self.assertNotIn('Outro dispositivo',rows[0]['text'])
 def test_long_article_retains_requested_concept_in_model_window(self):
  text='O segurado genérico. '*160+'Pescador artesanal e condições da atividade. '+'Final. '*150
  package={'norms':[{'excerpts':[{'text':text,'device':'art11','source':'https://www2.camara.leg.br/fonte'}]}]}
  row=legal_answer.sources(package,focus='aposentadoria pescador segurado especial')[0]
  self.assertIn('Pescador artesanal',row['text']);self.assertIn(row['text'],text)
 def test_unproven_individual_entitlement_cannot_become_draft_ground(self):
  for text in ['O requerente preenche os requisitos.','O requerente enquadra-se como segurado especial.']:
   with self.assertRaises(ValueError):draft.validate_claims({'paragraphs':[{'text':text}]})
  draft.validate_claims({'paragraphs':[{'text':'O requerente tem direito se comprovados todos os requisitos.'}]})
 def test_family_economy_alternative_cannot_become_universal_requirement(self):
  package={'norms':[{'excerpts':[{'text':'A atividade pode ser exercida individualmente ou em regime de economia familiar.'}]}]}
  rejected=[{'text':'A pesca em regime de economia familiar é fundamental para a caracterização do segurado especial.'}]
  self.assertEqual(len(draft.scope_issues(rejected,package)),1)
  self.assertEqual(len(draft.scope_issues([{'text':'O regime de economia familiar tem condições próprias. No caso de pescadores artesanais, a atividade deve ser exercida em mútua dependência.'}],package)),1)
  self.assertEqual(len(draft.scope_issues([{'text':'Economia familiar tem definição legal. Tal regime é requisito quando a atividade é exercida individualmente ou em regime de economia familiar.'}],package)),1)
  for value in ['A pesca pode ser exercida individualmente ou em regime de economia familiar.','Quando exercida em economia familiar, é necessário demonstrar suas condições.']:
   self.assertEqual(draft.scope_issues([{'text':value}],package),[])

class DraftPreflightTests(unittest.IsolatedAsyncioTestCase):
 async def test_failed_repair_preserves_only_independently_reviewed_arguments(self):
  import json
  from moara.gateway import chat_api
  def reply(value):return {'choices':[{'message':{'content':json.dumps(value)}}]}
  package={'norms':[{'source':'https://www2.camara.leg.br/fonte','excerpts':[{'device':'art3','text':'A modalidade depende de concordância das partes.'}]}]}
  initial=reply({'paragraphs':[{'text':'A modalidade depende de concordância.','support_ids':['L1.1:1']},{'text':'O benefício está automaticamente concedido.','support_ids':['L1.1:1']}]})
  review=reply({'checks':[{'index':0,'supported':True,'reason':''},{'index':1,'supported':False,'reason':'unsupported automatic entitlement'}]})
  invalid_repair=reply({'paragraphs':[{'text':'A Lei 8213/1191 concede automaticamente o benefício.','support_ids':['L1.1:1']}]})
  with patch.object(chat_api,'completion',AsyncMock(side_effect=[initial,review,invalid_repair])):
   result=await legal_answer.explain(None,None,'Explique a modalidade',package)
  self.assertEqual(result['status'],'grounded_explanation');self.assertIn('depende de concordância',result['answer'])
  self.assertNotIn('automaticamente',result['answer']);self.assertNotIn('1191',result['answer']);self.assertEqual(result['omitted_paragraph_count'],1)
 async def run_draft(self,question,has_text=True):
  package={'status':'official_sources_retrieved' if has_text else 'verification_unavailable','legal_conclusion_allowed':False,'norms':[{'excerpts':[{'device':'art48','text':'Texto oficial de exemplo, sem pretensão de lei real.'}]}] if has_text else [],'checked_at':'2026-11-02T00:00:00Z'}
  response=httpx.Response(200,json={'result':{'structuredContent':package}},request=httpx.Request('POST','http://mcp'))
  http=SimpleNamespace(post=AsyncMock(return_value=response))
  request=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(http=http)),scope={})
  with patch('moara.gateway.settings.secret',return_value='x'*40),patch.object(legal,'save',AsyncMock(return_value='draft-evidence')) as saved,patch.object(legal_answer,'explain',AsyncMock(return_value={'status':'grounded_explanation' if has_text else 'no_sources','answer':'Fundamento validado.' if has_text else None,'inference_used':has_text})),patch.object(legal,'recovery_topics',AsyncMock(return_value=[])):
   result=await legal.preflight([{'role':'user','content':question}],request,SimpleNamespace(user_id='test'),force=True)
  return result,http,saved
 async def test_exact_reported_question_produces_draft_instead_of_date_gate(self):
  result,http,saved=await self.run_draft(QUESTION+'\n'+draft.PORTAL_DRAFT)
  self.assertIn('PETIÇÃO INICIAL',result['answer']);self.assertIn('Fundamento validado',result['answer'])
  meta=result['legal_verification'];self.assertEqual(meta['reference_date_basis'],'current_date_for_draft_research_not_case')
  self.assertEqual(meta['answer_status'],'legal_draft_with_pending_fields');self.assertFalse(meta['legal_conclusion_allowed'])
  args=http.post.await_args.kwargs['json']['params']['arguments']
  self.assertEqual(args['reference_date'],str(today()));self.assertEqual(args['norms'][0]['number'],8213)
  self.assertEqual(args['query'],'aposentadoria pescador segurado especial');self.assertEqual(saved.await_count,1)
 async def test_explicit_historical_date_is_preserved(self):
  result,http,saved=await self.run_draft(QUESTION+' Data de referência: 15/06/2020.')
  self.assertEqual(result['legal_verification']['reference_date'],'2020-06-15')
  self.assertEqual(result['legal_verification']['reference_date_basis'],'explicit')
 async def test_source_failure_does_not_replace_petition_with_a_generic_question(self):
  result,http,saved=await self.run_draft(QUESTION,has_text=False)
  self.assertIn('PETIÇÃO INICIAL',result['answer']);self.assertIn('FUNDAMENTAÇÃO PENDENTE',result['answer'])
  self.assertNotIn('informe a data relevante',result['answer']);self.assertEqual(http.post.await_count,2)
 async def test_unknown_private_topic_has_safe_scaffold_without_public_http(self):
  result,http,saved=await self.run_draft('Crie uma petição para meu caso com anexo e CPF 123.456.789-00.')
  self.assertIn('Dos pedidos',result['answer']);self.assertEqual(http.post.await_count,0)
 async def test_public_research_does_not_receive_private_narrative(self):
  result,http,saved=await self.run_draft('Crie uma petição para minha aposentadoria de pescador segurado especial, CPF 123.456.789-00.')
  wire=http.post.await_args.kwargs['json']['params']['arguments']
  self.assertNotIn('CPF',str(wire));self.assertNotIn('123.456',str(wire))
 async def test_presentation_suffix_does_not_block_an_informational_question(self):
  result,http,saved=await self.run_draft('me explique a promoção na Lei 8112/1990.\n\n'+draft.PORTAL_DRAFT)
  self.assertEqual(result['legal_verification']['reference_date_basis'],'current_date_assumed_for_information')
  self.assertFalse(result['legal_verification']['draft'])
