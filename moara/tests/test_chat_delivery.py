import asyncio,json,unittest
from moara.gateway.chat_delivery import approved_stream

class ApprovedDeliveryTests(unittest.IsolatedAsyncioTestCase):
 async def test_unicode_and_whitespace_are_lossless_and_metadata_is_retained(self):
  text='Você é Moara.\n\n'+('Legislação ⚖️ e código.\n'*20)
  result={'id':'synthetic','model':'moara','moara':{'citation_validation':'passed'},'choices':[{'message':{'role':'assistant','content':text},'finish_reason':'stop'}]}
  chunks=[c async for c in approved_stream(result)]
  self.assertEqual(chunks[-1],'data: [DONE]\n\n')
  events=[json.loads(c[6:]) for c in chunks[:-1]]
  self.assertEqual(events[0]['moara'],result['moara'])
  fragments=[choice['delta'].get('content','') for e in events for choice in e.get('choices',[])]
  self.assertEqual(''.join(fragments),text);self.assertGreater(len(fragments),5)
 async def test_cancel_does_not_publish_remaining_text_or_done(self):
  generator=approved_stream({'choices':[{'message':{'role':'assistant','content':'x'*1000}}]})
  await anext(generator);first=await anext(generator)
  self.assertNotIn('[DONE]',first);self.assertLess(len(first),1000)
  await generator.aclose()
  with self.assertRaises(StopAsyncIteration):await anext(generator)
 async def test_delivery_keeps_tool_payload_and_finish_reason(self):
  call={'id':'call1','type':'function','function':{'name':'read','arguments':'{}'}}
  result={'choices':[{'message':{'role':'assistant','tool_calls':[call]},'finish_reason':'tool_calls'}]}
  chunks=[c async for c in approved_stream(result)]
  self.assertIn('"tool_calls"',chunks[0]);self.assertIn('"finish_reason":"tool_calls"',chunks[-2])
