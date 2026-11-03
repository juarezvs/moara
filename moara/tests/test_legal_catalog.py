import unittest,json,base64,gzip,hashlib,asyncio
from datetime import date
from types import SimpleNamespace
import httpx
from moara.legal_mcp.contracts import Norm,NormSearch,Bill,LegislativeHistory,identify
from moara.legal_mcp.catalog import search,legislative_history,originating_bill,related_changes,history_record,history
from moara.legal_mcp.sources import OfficialSources,validated_identity,extract
from moara.legal_mcp.server import create_app

class CatalogueTests(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_preserves_accepted_snapshots_and_records_interrupted_attempt(self):
        entered=asyncio.Event()
        async def handler(request):
            row={'id':12,'siglaTipo':'PL','numero':6814,'ano':2017}
            if request.url.path.endswith('/tramitacoes'):
                entered.set();await asyncio.Event().wait()
            return httpx.Response(200,json={'dados':row if request.url.path.endswith('/12') else [row]})
        spec=LegislativeHistory(bill=Bill(number=6814,year=2017),reference_date=date(2020,1,1));record=history_record(spec)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            task=asyncio.create_task(history(OfficialSources(client),spec,record))
            await asyncio.wait_for(entered.wait(),3);task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(len(record['snapshots']),2)
        self.assertEqual(record['bill']['number'],6814)
        self.assertEqual(record['source_checks'][-1]['failure'],'timeout_or_cancelled')
        self.assertEqual(record['source_checks'][-1]['status'],'unavailable')

    async def test_catalogue_checks_identity_and_does_not_claim_vigencia(self):
        payload={'ListaDocumento':{'documentos':{'documento':[
            {'id':'33','tipo':'LEI-n','numero':'14133','anoassinatura':'2021','normaNome':'Lei 14.133/2021'},
            {'id':'34','tipo':'LEI-n','numero':'14134','anoassinatura':'2021'}]}}}
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload))) as client:
            value=await search(client,NormSearch(number=14133,year=2021))
        self.assertEqual(len(value['candidates']),1);self.assertEqual(value['candidates'][0]['id'],'33')
        self.assertFalse(value['legal_conclusion_allowed'])
        snapshot=value['snapshots'][0];raw=gzip.decompress(base64.b64decode(snapshot['snapshot_gzip_base64']))
        self.assertEqual(hashlib.sha256(raw).hexdigest(),snapshot['sha256'])

    async def test_camara_filters_future_events_without_turning_current_metadata_into_past_status(self):
        urls=[]
        def handler(request):
            urls.append(str(request.url));self.assertEqual(request.headers['cache-control'],'no-cache')
            row={'id':12,'siglaTipo':'PL','numero':6814,'ano':2017,'statusProposicao':{'dataHora':'2026-01-01','descricaoSituacao':'Atual'}}
            if request.url.path.endswith('/tramitacoes'):
                return httpx.Response(200,json={'dados':[{'dataHora':'2018-01-01','sequencia':1},{'dataHora':'2026-01-01','sequencia':2},{'dataHora':'invalid'}]})
            return httpx.Response(200,json={'dados':row if request.url.path.endswith('/12') else [row]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            value=await legislative_history(client,LegislativeHistory(bill=Bill(number=6814,year=2017),reference_date=date(2020,1,1)))
        self.assertEqual(value['status'],'legislative_history_retrieved')
        self.assertEqual(len(value['events']),1);self.assertEqual(value['excluded_events'],2)
        self.assertFalse(value['normative_text']);self.assertFalse(value['current_metadata_at_collection']['is_historical_status'])
        self.assertIn('dataFim=2020-01-01',urls[-1]);self.assertEqual(len(value['snapshots']),3)

    async def test_ambiguous_bill_or_pagination_is_not_silently_chosen(self):
        for payload in [
            {'dados':[{'id':1,'siglaTipo':'PL','numero':1,'ano':2020},{'id':2,'siglaTipo':'PL','numero':1,'ano':2020}]},
            {'dados':[{'id':1,'siglaTipo':'PL','numero':1,'ano':2020}],'links':[{'rel':'next','href':'http://127.0.0.1/'}]},
        ]:
            seen=[]
            def handler(request):seen.append(str(request.url));return httpx.Response(200,json=payload)
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                value=await legislative_history(client,LegislativeHistory(bill=Bill(number=1,year=2020),reference_date=date(2020,1,1)))
            self.assertEqual(value['status'],'unconfirmed');self.assertEqual(len(seen),1)

    async def test_bill_unavailability_is_recorded_and_not_a_statement_of_no_changes(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(503))) as client:
            value=await legislative_history(client,LegislativeHistory(bill=Bill(number=1,year=2020),reference_date=date(2020,1,1)))
        self.assertEqual(value['source_checks'][0]['http_status'],503);self.assertEqual(value['status'],'unconfirmed')
        self.assertFalse(value['legal_conclusion_allowed'])

    async def test_future_history_makes_no_external_request(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:(_ for _ in ()).throw(AssertionError()))) as client:
            value=await legislative_history(client,LegislativeHistory(bill=Bill(number=1,year=2020),reference_date=date(2099,1,1)))
        self.assertEqual(value['source_checks'],[])

    async def test_correlated_norm_check_excludes_future_and_unrelated_devices(self):
        seen=[]
        def handler(request):
            seen.append(str(request.url))
            return httpx.Response(200,json={'DetalheDocumento':{'documentos':{'documento':[{'id':'3','identificacao':{'normaNome':'Norma alteradora'},'publicacoes':{}}]}}})
        changes=[{'codnormaposterior':'1','datapub':'01/01/2026','comentario':'Alteração'},
                 {'codnormaposterior':'2','datapub':'01/01/2019','comentario':'Alteração','itens':{'item':[{'dispositivo':'Art. 13'}]}},
                 {'codnormaposterior':'3','datapub':'01/01/2019','comentario':'Alteração','itens':{'item':[{'dispositivo':'Art. 12'}]}}]
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            value=await related_changes(OfficialSources(client),changes,['12'],date(2020,1,1))
        self.assertEqual(len(seen),1);self.assertTrue(seen[0].endswith('/3.json'));self.assertFalse(value['coverage_complete'])

    async def test_tools_have_strict_schemas_and_include_catalogue_and_history(self):
        app=create_app('z'*40)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://legal',headers={'Authorization':'Bearer '+'z'*40}) as client:
                r=await client.post('/mcp',json={'jsonrpc':'2.0','id':1,'method':'tools/list'})
                self.assertEqual({t['name'] for t in r.json()['result']['tools']},{'search_web','verify_legal_sources','search_federal_norms','consult_legislative_history','consult_procurement_limits','research_legal_sources','discover_federal_norms','recover_legal_sources','research_precedents_by_subject','discover_google_references','search_stf_thesis_catalog','search_legal_metadata'})
                for name in ['search_federal_norms','consult_legislative_history']:
                    r=await client.post('/mcp',json={'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':name,'arguments':{'url':'http://127.0.0.1/'}}})
                    self.assertEqual(r.json()['error']['code'],-32602)

class IdentityTests(unittest.TestCase):
    def test_norm_number_alone_does_not_authorize_a_different_year_kind_or_signature(self):
        spec=Norm(kind='LEI',number=14133,year=2021)
        ident={'numero':'14133','tipo':'LEI-n','dataassinatura':'01/04/2021','urlDocumento':'https://normas.leg.br/?urn=urn:lex:br:federal:lei:2021-04-01;14133'}
        self.assertTrue(validated_identity(ident,spec).endswith(';14133'))
        for change in [{'tipo':'LCP-n'},{'dataassinatura':'02/04/2021'}, {'urlDocumento':ident['urlDocumento'].replace('2021-','2020-')}]:
            with self.assertRaises(ValueError):validated_identity({**ident,**change},spec)

    def test_only_explicit_camara_origin_is_used_not_the_number_of_the_law(self):
        self.assertIsNone(originating_bill({'name':'Lei nº 14.133/2021'}))
        bill=originating_bill({'legislationSourceProcess':{'name':'Projeto de Lei (CD) nº 6814/2017 : Lei nº 14.133/2021'}})
        self.assertEqual((bill.kind,bill.number,bill.year),('PL',6814,2017))
        self.assertEqual(identify('EC 132/2023 art. 1')[0].kind,'EMC')

    def test_quoted_amendment_and_foreign_norm_are_not_selected_as_own_articles(self):
        base='urn:lex:br:federal:lei:2021-04-01;14133'
        root={'legislationIdentifier':base,'hasPart':[
            {'legislationIdentifier':base+'!art6','workExample':{'legislationDate':'2021-04-01','text':'Próprio'},'hasPart':[
                {'legislationIdentifier':base+'!art6_alt1','workExample':{'legislationDate':'2021-04-01','text':'Alteração de outra norma'}}]},
            {'legislationIdentifier':'urn:outra!art6','workExample':{'legislationDate':'2021-04-01','text':'Outra norma'}}]}
        values,gaps=extract(root,['6'],'2026-01-01')
        self.assertEqual([v['text'] for v in values],['Próprio']);self.assertTrue(gaps)

if __name__=='__main__':unittest.main()
