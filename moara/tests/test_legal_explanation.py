import json,unittest
from unittest.mock import AsyncMock,patch
from moara.gateway import legal_answer as a
from moara.legal_mcp import texts,discovery

def verdict(supported=True):
 return {'choices':[{'message':{'content':json.dumps({'checks':[{'index':0,'supported':supported,'reason':'Wrong actor' if not supported else ''}]})}}]}

class ExplanationTests(unittest.TestCase):
 def rows(self):
  return [{'id':'L1.1','device':'art3','text':'Art. 3. A modalidade alfa depende de concordância das partes.','source':'https://www2.camara.leg.br/alfa','norm':None},
          {'id':'L2.1','device':'art9','text':'Art. 9. A modalidade beta depende de prerrogativa expressa.','source':'https://www2.camara.leg.br/beta','norm':None}]
 def test_intent_is_generic_and_additive(self):
  self.assertEqual(a.answer_task('Explique a diferença entre alfa e beta'),'compare')
  self.assertEqual(a.answer_task('como funciona a modalidade alfa?'),'explain')
  self.assertEqual(a.answer_task('qual lei trata de alfa?'),'answer')
 def test_comparison_can_cite_both_checked_sources_in_one_paragraph(self):
  rows=self.rows();spans=a.evidence_spans(rows)
  points=a.composed_points({'paragraphs':[{'text':'Alfa depende de concordância; beta, de prerrogativa expressa.','support_ids':list(spans)}]},rows,spans)
  answer,used=a.render_points(points,rows)
  self.assertEqual(len(points),2);self.assertEqual(len(used),2)
  self.assertEqual(answer.count('Alfa depende'),1)
  for row in rows:self.assertIn(row['source'],answer)
 def test_unknown_evidence_and_unchecked_article_rejected(self):
  rows=self.rows();spans=a.evidence_spans(rows)
  for text,ids in [('Esta é uma explicação.',['fabricated']),('O art. 999 garante a modalidade.',['L1.1:1'])]:
   with self.assertRaises(ValueError):a.composed_points({'paragraphs':[{'text':text,'support_ids':ids}]},rows,spans)
 def test_spans_are_exact_and_bounded_even_for_large_source(self):
  rows=self.rows();rows[0]['text']=('Uma regra com várias palavras e exceções. '*70)
  spans=a.evidence_spans(rows)
  self.assertTrue(all(12<=len(s['quote'])<=600 and s['quote'] in next(r['text'] for r in rows if r['id']==s['source_id']) for s in spans.values()))
 def test_distinctive_terms_outrank_generic_server_mentions(self):
  ex=[{'device':'art1','text':'O servidor terá requisitos e remuneração.'}]*20+[{'device':'art3','text':'A cessão depende de concordância.'},{'device':'art9','text':'A requisição é ato irrecusável.'}]
  ranked=texts.relevant(ex,'explique a diferença entre cessão e requisição de servidor',limit=2)
  self.assertEqual({r['device'] for r in ranked},{'art3','art9'})
 def test_discovery_removes_instruction_and_tries_plural_without_inventing_law(self):
  variants=discovery.query_variants('diferença entre cessão requisição servidor')
  self.assertEqual(variants[:2],['cessão requisição','cessões requisições'])
  self.assertFalse(any(c.isdigit() for v in variants for c in v))
 def test_total_revocation_is_distinct_from_partial_amendments(self):
  url='https://www2.camara.leg.br/legin/fed/decret/2017/decreto-9144-22-agosto-2017-785368-norma-pe.html'
  page='<strong>Situação:</strong><span>Revogada</span><a href="../2021/decreto-10835-14-outubro-2021-791864-norma-pe.html">Decreto (Revogação).</a>'
  state=discovery.record_status(page,url)
  self.assertTrue(state['reported_revoked']);self.assertEqual(state['revoking_norms'][0]['norm']['number'],10835)
  self.assertFalse(discovery.record_status('<strong>Situação:</strong> Não consta revogação expressa. Revogação Parcial.',url)['reported_revoked'])
 def test_schema_constrains_output_to_real_evidence_ids(self):
  fmt=a.explanation_format(a.evidence_spans(self.rows()))
  self.assertEqual(fmt['type'],'json_schema')
  item=fmt['json_schema']['schema']['properties']['paragraphs']['items']
  self.assertEqual(item['properties']['support_ids']['items']['enum'],['L1.1:1','L2.1:1'])
 def test_incomplete_or_duplicate_review_is_rejected(self):
  for checks in [[],[{'index':0,'supported':True},{'index':0,'supported':True}],[{'index':0,'supported':'true'}]]:
   with self.assertRaises(ValueError):a.review_issues({'checks':checks},2)
 def test_requisition_actor_is_preserved_from_explicit_official_clause(self):
  quote='A requisição não será nominal e o órgão ou entidade requisitada poderá indicar o agente público.'
  text,changes=a.preserve_actor_attribution('Isso permite ao órgão requisitante indicar o agente público.',[quote])
  self.assertIn('órgão requisitado indicar',text);self.assertEqual(len(changes),1)
 def test_actor_guard_does_not_guess_without_unambiguous_same_verb(self):
  text='O órgão requisitante pode indicar o agente.'
  for quotes in [[],['O órgão requisitado tem exercício.'],['O órgão requisitado pode indicar A. O órgão requisitante pode indicar B.']]:
   self.assertEqual(a.preserve_actor_attribution(text,quotes),(text,[]))
 def test_actor_guard_keeps_correct_indication_and_gender(self):
  quote='A entidade requisitada poderá indicar o agente.'
  correct='A entidade requisitada pode indicar o agente.'
  self.assertEqual(a.preserve_actor_attribution(correct,[quote]),(correct,[]))
  changed,_=a.preserve_actor_attribution('A entidade requisitante pode indicar o agente.',[quote])
  self.assertIn('entidade requisitada',changed)

class GenerationTests(unittest.IsolatedAsyncioTestCase):
 async def test_rejected_supplement_does_not_erase_supported_explanation(self):
  from moara.gateway import chat_api
  package={'norms':[{'source':'https://www2.camara.leg.br/alfa','excerpts':[{'device':'art3','text':'Alfa exige concordância expressa das partes.'}]}]}
  draft={'choices':[{'message':{'content':json.dumps({'paragraphs':[{'text':'Alfa depende da concordância das partes.','support_ids':['L1.1:1']},{'text':'Um detalhe adicional que não foi confirmado.','support_ids':['L1.1:1']}]})}}]}
  review={'choices':[{'message':{'content':json.dumps({'checks':[{'index':0,'supported':True,'reason':''},{'index':1,'supported':False,'reason':'unsupported supplement'}]})}}]}
  with patch.object(chat_api,'completion',AsyncMock(side_effect=[draft,review,draft,review])):
   result=await a.explain(None,None,'explique alfa',package)
  self.assertEqual(result['status'],'grounded_explanation');self.assertEqual(result['omitted_paragraph_count'],1)
  self.assertIn('depende da concordância',result['answer']);self.assertNotIn('detalhe adicional',result['answer'])
 async def test_review_can_correct_actor_without_changing_literal_evidence(self):
  from moara.gateway import chat_api
  package={'norms':[{'source':'https://www2.camara.leg.br/alfa','excerpts':[{'device':'art9','text':'O órgão de origem poderá indicar o agente público.'}]}]}
  def reply(text):return {'choices':[{'message':{'content':json.dumps({'paragraphs':[{'text':text,'support_ids':['L1.1:1']}]})}}]}
  with patch.object(chat_api,'completion',AsyncMock(side_effect=[reply('O órgão de destino indica o agente público.'),verdict(False),reply('A indicação cabe ao órgão de origem.'),verdict()])):
   result=await a.explain(None,None,'explique quem indica',package)
  self.assertIn('órgão de origem',result['answer']);self.assertNotIn('órgão de destino',result['answer'])
  self.assertEqual(result['evidence_review'],'completed_not_a_legal_certificate')
 async def test_invalid_review_does_not_publish_unreviewed_draft(self):
  from moara.gateway import chat_api
  package={'norms':[{'source':'https://www2.camara.leg.br/alfa','excerpts':[{'device':'art9','text':'O órgão de origem poderá indicar o agente público.'}]}]}
  draft={'choices':[{'message':{'content':json.dumps({'paragraphs':[{'text':'Esta é a frase do rascunho.','support_ids':['L1.1:1']}]})}}]}
  with patch.object(chat_api,'completion',AsyncMock(side_effect=[draft,{'choices':[{'message':{'content':'invalid'}}]}])):
   result=await a.explain(None,None,'explique quem indica',package)
  self.assertEqual(result['status'],'quoted_sources_fallback');self.assertNotIn('frase do rascunho',result['answer'])
 async def test_explanation_of_conditions_adds_plain_language_instead_of_bypassing_model(self):
  from moara.gateway import chat_api
  package={'recovery':{'status':'official_text_recovered'},'norms':[{'source':'https://www2.camara.leg.br/alfa','excerpts':[{'device':'art32_cpt','text':'A modalidade é restrita às condições seguintes.'},{'device':'art32_cpt_inc1','text':'Inovação tecnológica e impossibilidade de definição prévia.'}]}]}
  value={'choices':[{'message':{'content':json.dumps({'paragraphs':[{'text':'As duas condições devem estar presentes em conjunto.','support_ids':['L1.2:1']}]})}}]}
  with patch.object(chat_api,'completion',AsyncMock(side_effect=[value,verdict()])) as model:
   result=await a.explain(None,None,'Explique os critérios desta modalidade',package)
  self.assertEqual(model.await_count,2);self.assertEqual(result['status'],'grounded_explanation')
  self.assertIn('em conjunto',result['answer']);self.assertIn('tecnológica e impossibilidade',result['points'][0]['quote'])
  self.assertIn('<details>',result['answer']);self.assertIn('tecnológica e impossibilidade',result['answer'])
 async def test_one_bounded_repair_preserves_comparison_and_evidence(self):
  from moara.gateway import chat_api
  package={'norms':[{'source':'https://www2.camara.leg.br/alfa','excerpts':[{'device':'art3','text':'Alfa exige concordância expressa das partes.'}]}]}
  invalid={'choices':[{'message':{'content':'{"paragraphs":[{"text":"Uma explicação.","support_ids":["fake"]}]}'}}]}
  valid={'choices':[{'message':{'content':json.dumps({'paragraphs':[{'text':'Alfa exige que as partes concordem expressamente.','support_ids':['L1.1:1']}]})}}]}
  with patch.object(chat_api,'completion',AsyncMock(side_effect=[invalid,valid,verdict()])) as model:
   result=await a.explain(None,None,'explique alfa',package)
  self.assertEqual(model.await_count,3);self.assertEqual(result['status'],'grounded_explanation')
  self.assertEqual(result['generation_attempts'],2);self.assertIn('concordem',result['answer'])
  self.assertEqual(result['points'][0]['quote'],package['norms'][0]['excerpts'][0]['text'])
 async def test_repeated_invalid_model_output_never_becomes_verified_explanation(self):
  from moara.gateway import chat_api
  package={'norms':[{'source':'https://www2.camara.leg.br/alfa','excerpts':[{'device':'art3','text':'Alfa exige concordância expressa das partes.'}]}]}
  with patch.object(chat_api,'completion',AsyncMock(return_value={'choices':[{'message':{'content':'invalid'}}]})) as model:
   result=await a.explain(None,None,'explique alfa',package)
  self.assertEqual(model.await_count,2);self.assertEqual(result['status'],'quoted_sources_fallback')
  self.assertEqual(len(result['validation_rejections']),2)
