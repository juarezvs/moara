import unittest
from datetime import date,timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
import httpx
from moara.legal_mcp import procurement
from moara.legal_mcp.contracts import today,ProcurementLimits,identify
from moara.gateway import legal_verification as legal

INDEX='<a href="https://www.in.gov.br/test">DECRETO Nº 12.807, DE 29 DE DEZEMBRO DE 2025</a>'
TABLE='''<div id="parent-fieldname-text">Lei 14.133/2021. Decreto n.º 12.807, de 29 de dezembro de 2025. Valores que entrarão em vigor a partir de 1º de janeiro de 2026.
<table><tr><th>Dispositivo</th><th>Valor</th></tr>
<tr><td>Art. 75, inciso I: Obras</td><td>R$ 123.456,78 (por extenso)</td></tr>
<tr><td>Art. 75, inciso II: Compras</td><td>R$ 61.728,39</td></tr>
<tr><td>Art. 75, inciso IV, alínea c</td><td>R$ 999.999,99</td></tr></table></div>'''

class OfficialTableTests(unittest.TestCase):
    def parse(self,table=TABLE,index=INDEX,at=date(2026,10,30)):
        with patch.object(procurement,'today',return_value=date(2026,10,30)):
            return procurement.extract_limits(index,table,at)
    def test_values_are_extracted_and_not_fixed_or_confused_with_other_inciso(self):
        value=self.parse();self.assertEqual([r['amount_brl'] for r in value['rows']],['123.456,78','61.728,39'])
        self.assertEqual(self.parse(TABLE.replace('123.456,78','111.111,11'))['rows'][0]['amount_brl'],'111.111,11')
    def test_changed_pncp_or_missing_effective_year_blocks_stale_table(self):
        for table,index in [(TABLE,INDEX.replace('12.807','13.999')),(TABLE.replace('janeiro de 2026','janeiro de 2027'),INDEX),(TABLE.replace('entrarão em vigor a partir','foram publicados'),INDEX)]:
            with self.assertRaises(ValueError):self.parse(table,index)
    def test_historical_or_future_query_never_uses_current_table(self):
        for at in [date(2024,1,1),date(2026,10,29),date(2027,1,1)]:
            with self.assertRaises(ValueError):self.parse(at=at)
    def test_duplicate_missing_or_ambiguous_row_fails_closed(self):
        for table in [TABLE.replace('inciso II:','inciso III:'),TABLE.replace('R$ 61.728,39','R$ 61.728,39 e R$ 62.000,00'),TABLE.replace('</table>','<tr><td>Art. 75, inciso I:</td><td>R$ 12,00</td></tr></table>')]:
            with self.assertRaises(ValueError):self.parse(table)

class InformationGateTests(unittest.IsolatedAsyncioTestCase):
    async def preflight(self,question,package=None):
        if package is None:package={'status':'official_information_unavailable','legal_conclusion_allowed':False}
        response=httpx.Response(200,json={'result':{'structuredContent':package}},request=httpx.Request('POST','http://mcp'))
        http=SimpleNamespace(post=AsyncMock(return_value=response));request=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(http=http)))
        with patch('moara.gateway.settings.secret',return_value='x'*40),patch.object(legal,'save',AsyncMock(return_value='test-evidence')) as saved:
            answer=await legal.preflight([{'role':'user','content':question}],request,None,force=True)
        return answer,http,saved
    async def test_exact_reported_question_uses_current_mcp_without_clarification(self):
        question='me mostre o limite financeiro para dispensa de licitação previsto na lei 14133/2021.'
        answer,http,saved=await self.preflight(question)
        rpc=http.post.await_args.kwargs['json']['params']
        self.assertEqual(rpc['name'],'consult_procurement_limits');self.assertEqual(rpc['arguments'],{'reference_date':str(today())})
        self.assertNotEqual(answer['legal_verification']['status'],'clarification_required');self.assertEqual(saved.await_count,1)
        self.assertFalse(answer['legal_verification']['legal_conclusion_allowed']);self.assertNotIn('R$',answer['answer'])
    async def test_case_or_ambiguous_historical_date_cannot_assume_today(self):
        for question in ['Posso dispensar a licitação no meu caso pela Lei 14133/2021?',
                         'Qual o limite da Lei 14133/2021 em 2024?',
                         'Qual o limite da Lei 14133/2021, data dos fatos: 31/02/2026?']:
            result=await legal.preflight([{'role':'user','content':question}],None,None,force=True)
            self.assertEqual(result['legal_verification']['status'],'clarification_required')
    async def test_model_is_not_allowed_to_generate_values_on_source_failure(self):
        answer,_,_=await self.preflight('Qual o valor para dispensa na Lei 14133/2021?')
        self.assertFalse(answer['legal_verification']['inference_used']);self.assertIn('Não consegui confirmar',answer['answer'])
    def test_render_is_literal_sourced_and_does_not_authorize_a_case(self):
        self.assertTrue(legal.informational_query('Qual o limite de dispensa no caso de obras na Lei 14133/2021?'))
        for question in ['Qual o limite para dispensa do art. 75, inciso IV da Lei 14133/2021?', 'Qual o limite de dispensa do art. 95 da Lei 14133/2021?']:
            self.assertFalse(legal.procurement_query(question,identify(question)))
        with patch.object(procurement,'today',return_value=date(2026,10,30)):data=procurement.extract_limits(INDEX,TABLE,date(2026,10,30))
        package={**data,'status':'official_information_retrieved','reference_date':'2026-10-30','basis_source':'https://normas.leg.br/','gaps':[]}
        text=legal.render_procurement(package,'test-evidence')
        self.assertIn('123.456,78',text);self.assertIn('61.728,39',text);self.assertIn('valores inferiores',text)
        self.assertIn('12.807/2025',text);self.assertIn('contratação concreta',text)

class AdapterFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_official_source_means_no_values_and_no_old_cache(self):
        with patch.object(procurement.OfficialSources,'fetch',AsyncMock(side_effect=httpx.ConnectError('offline'))):
            value=await procurement.consult(SimpleNamespace(),ProcurementLimits(reference_date=today()))
        self.assertEqual(value['rows'],[]);self.assertEqual(value['status'],'official_information_unavailable')
        self.assertFalse(value['legal_conclusion_allowed'])
