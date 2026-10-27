import asyncio, importlib.util, unittest
from unittest.mock import AsyncMock, patch
import aiohttp
from pathlib import Path
spec=importlib.util.spec_from_file_location('progress',Path(__file__).with_name('moara_file_progress.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ProgressTests(unittest.IsolatedAsyncioTestCase):
 async def test_measured_batches(self):
  updates=AsyncMock();operation=AsyncMock(side_effect=lambda batch,**kw:[[1] for _ in batch])
  with patch.object(m,'publish_progress',updates):
   result=await m.embed_with_progress(operation,list(range(35)),file_id='test',batch_size=16)
  self.assertEqual(len(result),35)
  self.assertEqual([len(x.args[0]) for x in operation.call_args_list],[16,16,3])
  self.assertEqual([x.args[2] for x in updates.call_args_list],[0,16,32,35,35])
  self.assertEqual(updates.call_args_list[-1].args[1],'saving')
 async def test_incomplete_never_advances(self):
  updates=AsyncMock()
  with patch.object(m,'publish_progress',updates):
   with self.assertRaises(ValueError):await m.embed_with_progress(AsyncMock(return_value=[]),['x'],file_id='test')
  self.assertEqual(updates.await_count,1)
 async def test_retry_same_batch(self):
  error=aiohttp.ClientResponseError(None,(),status=429,headers={'Retry-After':'10'})
  op=AsyncMock(side_effect=[error,[[1]]])
  with patch.object(m.asyncio,'sleep',AsyncMock()) as sleep:
   result=await m.with_embedding_retry(op)('model',['x'],'http://gateway:8000/v1')
  self.assertEqual(result,[[1]]);self.assertEqual(op.call_args_list[0],op.call_args_list[1]);sleep.assert_awaited_once_with(10)
 async def test_other_provider_not_retried(self):
  op=AsyncMock(side_effect=aiohttp.ClientResponseError(None,(),status=429))
  with self.assertRaises(aiohttp.ClientResponseError):await m.with_embedding_retry(op)('model',['x'],'https://other.example/v1')
  self.assertEqual(op.await_count,1)
 async def test_auth_failure_not_retried(self):
  op=AsyncMock(side_effect=aiohttp.ClientResponseError(None,(),status=401))
  with self.assertRaises(aiohttp.ClientResponseError):await m.with_embedding_retry(op)('model',['x'],'http://gateway:8000/v1')
  self.assertEqual(op.await_count,1)
 async def test_exhausted_retry_is_bounded(self):
  op=AsyncMock(side_effect=aiohttp.ClientResponseError(None,(),status=429))
  with patch.object(m.asyncio,'sleep',AsyncMock()):
   with self.assertRaises(aiohttp.ClientResponseError):await m.with_embedding_retry(op)('model',['x'],'http://gateway:8000/v1')
  self.assertEqual(op.await_count,6)
 async def test_cancellation_propagates(self):
  op=AsyncMock(side_effect=asyncio.CancelledError())
  with self.assertRaises(asyncio.CancelledError):await m.with_embedding_retry(op)('model',['x'],'http://gateway:8000/v1')
  self.assertEqual(op.await_count,1)
 def test_retry_after(self):
  self.assertEqual(m.retry_delay({'Retry-After':'120'},0),120)
  self.assertEqual(m.retry_delay({'Retry-After':'invalid'},0),2)
  self.assertEqual(m.retry_delay({'Retry-After':'NaN'},0),2)
  self.assertFalse(m.local_gateway((),{'url':'http://gateway:8000/v1?x=1'}))
if __name__=='__main__':unittest.main()
