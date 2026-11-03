from pathlib import Path
p=Path('moara/webui/auto-documents/test_automatic_documents.py');s=p.read_text(encoding='utf-8')
old=""" async def test_history_budget_fails_explicitly(self):
  self.body['messages'].insert(0,{'role':'assistant','content':'x'*20000})
  with self.assertRaises(HTTPException) as error:await m.prepare_documents(None,self.body,{'id':'user'},{})
  self.assertEqual(error.exception.status_code,413)
"""
new=""" async def test_large_history_is_compacted_without_reupload(self):
  import copy
  self.body['messages'].insert(0,{'role':'assistant','content':'x'*20000})
  saved=self.body['messages'];snapshot=copy.deepcopy(saved)
  emit=AsyncMock()
  body,sources,handled=await m.prepare_documents(None,self.body,{'id':'user'},{'__event_emitter__':emit})
  self.assertEqual(saved,snapshot);self.assertEqual(body['messages'][-1],snapshot[-1])
  self.assertIn('30/11/2026',sources[0]['document'][0]);self.assertTrue(handled)
  self.assertTrue(any(c.args[0]['data']['action']=='moara_compacting_history' for c in emit.call_args_list))
  self.assertLess(m.prompt_size(body['messages'],[]),19000)
 def test_current_question_is_never_cut(self):
  messages=[{'role':'user','content':'ação '*12000}]
  with self.assertRaises(HTTPException):m.compact_document_history(messages,[],1)
 def test_system_instructions_cannot_be_dropped(self):
  messages=[{'role':'system','content':'policy '*3000},{'role':'user','content':'Pergunta'}]
  with self.assertRaises(HTTPException):m.compact_document_history(messages,[],1)
 def test_recent_tool_pair_stays_together_and_first_user_is_remembered(self):
  import copy
  messages=[{'role':'system','content':'Política imutável.'},{'role':'user','content':'Sou da NUTEC; não atribua a mim tarefas da SECAD.'},
   {'role':'assistant','content':'histórico '*4000},
   {'role':'user','content':'Qual o prazo?'},
   {'role':'assistant','content':None,'tool_calls':[{'id':'a','type':'function','function':{'name':'view_file','arguments':'{}'}}]},
   {'role':'tool','tool_call_id':'a','content':'Prazo: 30/11/2026.'},
   {'role':'assistant','content':'O prazo é 30/11/2026.'},
   {'role':'user','content':'E a minha providência?'}]
  saved=copy.deepcopy(messages);result,changed=m.compact_document_history(messages,[],1)
  self.assertTrue(changed);self.assertEqual(messages,saved);self.assertEqual(result[-1],messages[-1])
  self.assertIn(messages[0],result)
  self.assertIn('Sou da NUTEC',str(result))
  calls={c['id'] for x in result for c in x.get('tool_calls',[])}
  replies={x['tool_call_id'] for x in result if x.get('role')=='tool'}
  self.assertEqual(calls,replies)
 def test_active_tool_chain_is_preserved(self):
  old=[{'role':'user','content':'Antes'},{'role':'assistant','content':'antigo '*5000}]
  current=[{'role':'user','content':'Leia agora'},{'role':'assistant','content':None,'tool_calls':[{'id':'b'}]},{'role':'tool','tool_call_id':'b','content':'resultado atual'}]
  result,changed=m.compact_document_history(old+current,[],1)
  self.assertTrue(changed);self.assertEqual(result[-3:],current)
"""
assert old in s;s=s.replace(old,new);p.write_text(s,encoding='utf-8')
