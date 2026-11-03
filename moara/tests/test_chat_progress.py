import asyncio,json,unittest
from types import SimpleNamespace
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from moara.gateway.chat_progress import with_progress,publish

class ProgressTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_delivers_real_stage_before_slow_operation_finishes(self):
        request=SimpleNamespace(scope={});release=asyncio.Event()
        async def operation():
            publish(request,'retrieving_documents')
            await release.wait()
            async def content():yield 'data: {"choices":[]}\n\n';yield 'data: [DONE]\n\n'
            return StreamingResponse(content())
        response=with_progress(request,operation);iterator=response.body_iterator
        first=await asyncio.wait_for(anext(iterator),1)
        self.assertIn('retrieving_documents',first);self.assertFalse(release.is_set())
        release.set();remaining=[chunk async for chunk in iterator]
        self.assertEqual(remaining[-1],'data: [DONE]\n\n');self.assertNotIn('_moara_chat_progress',request.scope)

    async def test_disconnect_cancels_pending_work(self):
        request=SimpleNamespace(scope={});cancelled=asyncio.Event()
        async def operation():
            try:
                publish(request,'generating_response')
                await asyncio.Event().wait()
            finally:cancelled.set()
        iterator=with_progress(request,operation).body_iterator
        await asyncio.wait_for(anext(iterator),1)
        await asyncio.wait_for(iterator.aclose(),1)
        self.assertTrue(cancelled.is_set());self.assertEqual(request.scope,{})

    async def test_application_error_survives_as_error_without_success_marker(self):
        async def operation():raise HTTPException(403,'profile_not_authorized')
        chunks=[v async for v in with_progress(SimpleNamespace(scope={}),operation).body_iterator]
        value=json.loads(chunks[0].removeprefix('data: '))
        self.assertEqual(value['error']['status'],403)
        self.assertEqual(value['error']['code'],'profile_not_authorized')
        self.assertNotIn('[DONE]',''.join(chunks))

    async def test_unknown_stage_is_never_presented_as_a_completed_operation(self):
        request=SimpleNamespace(scope={});seen=[]
        request.scope['_moara_chat_progress']=seen.append
        publish(request,'invented_jurisprudence_research')
        self.assertEqual(seen,[])

if __name__=='__main__':unittest.main()
