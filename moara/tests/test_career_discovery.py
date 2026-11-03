import unittest
from types import SimpleNamespace
from unittest.mock import patch,AsyncMock
from urllib.parse import urlsplit,parse_qs
import httpx
from moara.legal_mcp import discovery,research
from moara.legal_mcp.contracts import SubjectSearch,Norm,Research,today

def row(number,summary):
 return '<li class="busca-resultados__item"><h3><a href="https://www2.camara.leg.br/legin/fed/lei/2000/lei-'+str(number)+'-1-janeiro-2000-1234-norma-pl.html">Lei '+str(number)+'</a></h3><p class="busca-resultados__descricao">Ementa: '+summary+'</p></li>'

class CareerDiscoveryTests(unittest.IsolatedAsyncioTestCase):
 async def test_identity_question_uses_recovered_official_metadata_without_a_model_answer(self):
  from moara.gateway.legal_answer import explain
  package={'recovery':{'status':'official_text_recovered'},'norms':[{'norm':{'kind':'LEI','number':55555,'year':2000},'excerpts':[{'device':'identificacao','text':'Lei 55555/2000 — Dispõe sobre carreiras dos servidores do Poder Judiciário.','source':'https://www2.camara.leg.br/official'}]}]}
  with patch('moara.gateway.chat_api.completion',AsyncMock()) as model:
   result=await explain(None,None,'qual a lei de cargos e salários do judiciário federal?',package)
  self.assertEqual(result['status'],'official_identity_answer');self.assertIn('55555',result['answer']);model.assert_not_called()
 def test_public_pay_vocabulary_is_reformulated_without_inventing_a_statute(self):
  variants=discovery.query_variants('cargos salários judiciário federal')
  self.assertEqual(variants[0],'carreiras servidores judiciário união')
  self.assertTrue(all(not any(c.isdigit() for c in q) for q in variants))
  self.assertEqual(discovery.query_variants('cargos salarios judiciario federal')[0],variants[0])
 def test_other_employers_and_magistrate_scope_are_not_replaced_by_judiciary_staff(self):
  variants=discovery.query_variants('cargos salários polícia federal')
  self.assertIn('polícia federal',variants[0]);self.assertNotIn('judiciário',variants[0])
  self.assertEqual(discovery.query_variants('salários cargos magistrados federal'),['salários cargos magistrados federal'])
  self.assertEqual(discovery.query_variants('crimes trânsito'),['crimes trânsito'])
 async def test_query_variants_find_an_arbitrary_official_career_law_not_a_hardcoded_answer(self):
  html=row(55555,'Dispõe sobre as carreiras dos servidores do Poder Judiciário da União.')
  async def tracked(adapter,url,result,expected):
   return html if parse_qs(urlsplit(url).query).get('geral')==['carreiras servidores judiciário união'] else '<html>Sem resultados</html>'
  with patch.object(discovery,'tracked',side_effect=tracked):
   result=await discovery.discover(SimpleNamespace(),SubjectSearch(query='cargos salários judiciário federal'))
  self.assertEqual(result['candidates'][0]['norm']['number'],55555)
  self.assertEqual(result['candidates'][0]['discovered_by_query'],result['query_variants'][0])
 async def test_failure_in_one_query_preserves_successful_official_discovery(self):
  html=row(55555,'Dispõe sobre as carreiras dos servidores do Poder Judiciário da União.')
  async def tracked(adapter,url,result,expected):
   if parse_qs(urlsplit(url).query).get('geral')==['carreiras servidores judiciário união']:return html
   raise httpx.ReadTimeout('fixture')
  with patch.object(discovery,'tracked',side_effect=tracked):result=await discovery.discover(SimpleNamespace(),SubjectSearch(query='cargos salários judiciário federal'))
  self.assertEqual(result['status'],'official_candidates_retrieved')
 async def test_camara_current_compilation_identity_is_attributed_to_its_real_source(self):
  n=Norm(kind='LEI',number=55555,year=2000);url='https://www2.camara.leg.br/legin/fed/lei/2000/lei-55555-1-janeiro-2000-1234-norma-pl.html';current=url.replace('-norma-','-normaatualizada-')
  metadata=row(55555,'Dispõe sobre as carreiras dos servidores do Poder Judiciário da União.')
  body='<html><p>Lei 55555 de 2000</p><p>Art. 1. As carreiras dos servidores do Poder Judiciário da União passam a ser regidas por esta Lei.</p></html>'
  with patch.object(discovery,'tracked',AsyncMock(side_effect=[metadata,'<html><a href="'+current+'">Texto Atualizado</a></html>',body])):
   record={'gaps':[]};await discovery.current_camara(None,n,today(),record)
  self.assertEqual(record['identity_source'],url);self.assertTrue(record['summary'])
  record.update(norm=n.model_dump(),excerpts=[{'device':'art1','text':'Carreiras dos servidores públicos.','source':current}])
  with patch.object(research.OfficialSources,'norm',AsyncMock(return_value=record)):
   result=await research.research(SimpleNamespace(),Research(reference_date=today(),norms=[n],subject_query='carreiras servidores'))
  self.assertEqual(result['norms'][0]['excerpts'][0]['source'],url)
