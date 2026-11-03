import unittest,uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
import httpx
from moara.identity import load_identity
from moara.gateway import orchestration,institutional,legal_verification as legal
from moara.gateway.rbac import Actor

def user(text):return {'role':'user','content':text}

class IdentityRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_capability_wording_is_canonical_even_after_legal_turns(self):
        identity=load_identity();old_hash=identity.sha256
        for question in ['quais suas habilidades?','o que você pode fazer?','Quais são suas habilidades?',
                         'Oi, como você pode me ajudar?','Quais suas funcionalidades, por favor?']:
            body=SimpleNamespace(messages=[user('Explique a Lei 14.133/2021'),{'role':'assistant','content':'Informe a data'},user(question)])
            request=SimpleNamespace(scope={})
            with patch.object(orchestration,'semantic_assessment',AsyncMock(side_effect=AssertionError('Do not classify self-help as law'))):
                context,answer,identity_question=await orchestration.prepare(body,request,None,identity,uuid.uuid4())
            self.assertTrue(identity_question);self.assertIsNone(context)
            result=await institutional.answer(identity,question,None,None)
            self.assertEqual(result['faq_id'],'capabilities');self.assertFalse(result['inference_used'])
            self.assertIn('seis especialidades',result['answer'])
        self.assertEqual(identity.sha256,old_hash)

    def test_mixed_requests_do_not_bypass_legal_policy(self):
        identity=load_identity()
        for text in ['O que você pode fazer? Explique a Lei 14133/2021.',
                     'Quais suas habilidades jurídicas para analisar o art. 6º?']:
            self.assertIsNone(identity.resolve(text))

    async def test_short_date_reply_is_routed_to_the_pending_norm(self):
        identity=load_identity()
        actor=Actor(uuid.uuid4(),'test:repair','Synthetic',None,(),frozenset({'*'}))
        context={'id':'juridica','name':'Moara Jurídica','version':'2.0.0','revision':1,'prompt_sha256':'x',
                 'policy_version':'2.0.0','tools':['normas.read']}
        request=SimpleNamespace(scope={},app=SimpleNamespace(state=SimpleNamespace(db=SimpleNamespace(audit=AsyncMock()))))
        body=SimpleNamespace(messages=[user('me explique o art. 6º da lei 14133/2021'),user('hoje')],document_ids=[],assistant_id='auto',model='auto')
        with patch('moara.gateway.catalog_api.visible_profiles',AsyncMock(return_value=[{'id':'gemma4-12b'}])),patch.object(orchestration.assistants,'resolve',AsyncMock(return_value=context)),patch.object(orchestration,'semantic_assessment',AsyncMock(side_effect=AssertionError('Do not reclassify the date'))):
            result,canonical,_=await orchestration.prepare(body,request,actor,identity,uuid.uuid4())
        self.assertTrue(result['requires_legal_sources']);self.assertIsNone(canonical)
        self.assertEqual(result['public']['reason'],'pending_legal_date_reply')

class LegalConversationTests(unittest.IsolatedAsyncioTestCase):
    async def captured_spec(self,messages):
        http=SimpleNamespace(post=AsyncMock(side_effect=httpx.ConnectError('synthetic outage')))
        request=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(http=http)))
        with patch('moara.gateway.settings.secret',return_value='x'*40),patch.object(legal,'save',AsyncMock(return_value='synthetic-evidence')):
            result=await legal.preflight(messages,request,None,force=True)
        spec=http.post.await_args.kwargs['json']['params']['arguments']
        self.assertFalse(result['legal_verification']['legal_conclusion_allowed'])
        return spec

    async def test_bare_historical_date_retains_norm_and_article(self):
        spec=await self.captured_spec([user('me explique o art. 6º da lei 14133/2021'),{'role':'assistant','content':'CPC art.12 hoje'},user('15/06/2022')])
        self.assertEqual(spec['reference_date'],'2022-06-15')
        self.assertEqual([(n['number'],n['articles']) for n in spec['norms']],[(14133,['6'])])

    async def test_today_reply_continues_the_pending_question(self):
        from moara.legal_mcp.contracts import today
        spec=await self.captured_spec([user('Lei 14133/2021, art.6'),user('hoje')])
        self.assertEqual(spec['reference_date'],str(today()))

    async def test_new_explicit_norm_does_not_mix_older_articles(self):
        spec=await self.captured_spec([user('CPC, art.12, hoje'),user('Lei 14133/2021, art.6, data de referência: 2022-06-15')])
        self.assertEqual([(n['number'],n['articles']) for n in spec['norms']],[(14133,['6'])])

    async def test_invalid_date_reply_does_not_reuse_older_date(self):
        result=await legal.preflight([user('CPC art.12, data de referência: 2020-01-01'),user('31/02/2022')],None,None,force=True)
        self.assertEqual(result['legal_verification']['status'],'clarification_required')

    def test_unrelated_turn_breaks_pending_date_context(self):
        self.assertIsNone(legal.pending_norm_text([user('CPC, art.12'),user('Quais suas habilidades?'),user('hoje')]))

    async def test_informational_article_defaults_to_current_date(self):
        from moara.legal_mcp.contracts import today
        spec=await self.captured_spec([user('me explique o art. 6 da lei 14133/2021')])
        self.assertEqual(spec['reference_date'],str(today()))
        self.assertEqual(spec['norms'][0]['articles'],['6'])

    async def test_case_date_is_still_required(self):
        result=await legal.preflight([user('Posso contratar no meu caso pela Lei 14133/2021?')],None,None,force=True)
        self.assertEqual(result['legal_verification']['status'],'clarification_required')

    async def test_new_informational_query_does_not_inherit_historical_date(self):
        from moara.legal_mcp.contracts import today
        spec=await self.captured_spec([user('CPC art.12; data dos fatos: 2020-01-01'),user('Qual o texto do art.6 da Lei 14133/2021?')])
        self.assertEqual(spec['reference_date'],str(today()))
