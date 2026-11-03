import json,unittest,uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from fastapi import HTTPException
from moara.gateway import project_tree as tree,project_agent as agent,platform_development as api
from moara.gateway.platform_contracts import validate_body
from moara.gateway.rbac import Actor

class TreeTests(unittest.TestCase):
 def test_nested_empty_folders_move_and_delete_are_versionable(self):
  original={'files':{'src/main.py':'print(1)'}}
  new=tree.apply(original,[{'op':'mkdir','path':'tests/unit'},{'op':'move','path':'src','destination':'app'}])
  self.assertEqual(new['files'],{'app/main.py':'print(1)'})
  self.assertIn('tests/unit',new['directories']);self.assertIn('src/main.py',original['files'])
  deleted=tree.apply(new,[{'op':'delete','path':'app','recursive':True}])
  self.assertEqual(deleted['files'],{});self.assertEqual(original['files'],{'src/main.py':'print(1)'})
 def test_write_requires_current_digest_and_replace_exact_match(self):
  original={'files':{'main.py':'hello world'}}
  with self.assertRaises(HTTPException):tree.apply(original,[{'op':'write','path':'main.py','content':'oops'}])
  result=tree.apply(original,[{'op':'replace','path':'main.py','old':'world','new':'Moara','expected_sha256':tree.sha('hello world')}])
  self.assertEqual(result['files']['main.py'],'hello Moara')
 def test_rejects_escape_and_platform_reserved_paths(self):
  for name in ['../x','/tmp/x','C:/x','a\\x','a/../x','CON','a/NUL.txt','a.','a//b','.git/config']:
   with self.subTest(name=name),self.assertRaises(HTTPException):tree.apply({'files':{}},[{'op':'mkdir','path':name}])
 def test_rejects_collisions_and_move_into_self(self):
  for op in [{'op':'move','path':'src','destination':'src/child'},{'op':'move','path':'src','destination':'dst'},{'op':'write','path':'SRC','content':'x'}]:
   with self.assertRaises(HTTPException):tree.apply({'files':{'src/a':'a','dst/b':'b'}},[op])
 def test_batch_failure_preserves_original(self):
  original={'files':{'one':'1'}}
  with self.assertRaises(HTTPException):tree.apply(original,[{'op':'write','path':'two','content':'2'},{'op':'delete','path':'absent'}])
  self.assertEqual(original,{'files':{'one':'1'}})
 def test_nonempty_delete_requires_recursive(self):
  with self.assertRaises(HTTPException):tree.apply({'files':{'a/b':'x'}},[{'op':'delete','path':'a'}])
 def test_contract_and_tree_share_folder_validation(self):
  validate_body('project',{'files':{'src/main.py':'x'},'directories':['empty']})
  with self.assertRaises(HTTPException):validate_body('project',{'files':{'src':'x'},'directories':['src/child']})
  with self.assertRaises(HTTPException):validate_body('project',{'files':{'Src':'x','src/child':'y'}})

def tool(op,identifier='call1'):
 op=dict(op);name='project_'+op.pop('op')
 return {'choices':[{'finish_reason':'tool_calls','message':{'role':'assistant','content':None,'tool_calls':[{'id':identifier,'type':'function','function':{'name':name,'arguments':json.dumps(op)}}]}}]}
def final():
 return {'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':'Concluido.'}}]}

class AgentTests(unittest.IsolatedAsyncioTestCase):
 async def test_real_operations_are_staged_not_host_writes(self):
  model=AsyncMock(side_effect=[tool({'op':'list'}),tool({'op':'write','path':'src/new.py','content':'print(2)'}),final()])
  original={'files':{}}
  new,receipts,text=await agent.run(None,None,original,'Crie um arquivo',model_call=model)
  self.assertEqual(new['files'],{'src/new.py':'print(2)'})
  self.assertEqual(original,{'files':{}});self.assertEqual(len(receipts),1)
 async def test_delete_permission_is_application_controlled(self):
  model=AsyncMock(side_effect=[tool({'op':'delete','path':'keep.py'})]+[final() for _ in range(11)])
  with self.assertRaises(HTTPException):await agent.run(None,None,{'files':{'keep.py':'safe'}},'Analise',False,model)
  self.assertIn('project_delete_not_authorized',model.await_args_list[1].args[0].messages[-1]['content'])
 async def test_narrow_write_contract_requires_actual_content(self):
  model=AsyncMock(side_effect=[tool({'op':'write','path':'new.py','content':'ok'}),final()])
  new,_,_=await agent.run(None,None,{'files':{}},'Crie',model_call=model)
  self.assertEqual(new['files']['new.py'],'ok')
 async def test_read_only_question_uses_content_without_write(self):
  model=AsyncMock(side_effect=[tool({'op':'read','path':'a.py'}),final()])
  new,receipts,_=await agent.run(None,None,{'files':{'a.py':'safe'}},'Explique',model_call=model)
  self.assertEqual(receipts,[]);self.assertEqual(new['files']['a.py'],'safe')
 async def test_truncation_and_step_limit_never_return_partial_commit(self):
  model=AsyncMock(return_value=tool({'op':'list'}))
  with self.assertRaises(HTTPException):await agent.run(None,None,{'files':{}},'Tarefa',model_call=model)
  self.assertEqual(model.await_count,12)
  model=AsyncMock(return_value={'choices':[{'finish_reason':'length','message':{'content':'partial'}}]})
  with self.assertRaises(HTTPException):await agent.run(None,None,{'files':{}},'Tarefa',model_call=model)

class EndpointTests(unittest.IsolatedAsyncioTestCase):
 def actor(self):
  return Actor(uuid.uuid4(),'qa','QA',None,('developer',),frozenset({'workspace.use','development.use','chat.use'}),session_id=uuid.uuid4())
 async def test_stale_version_is_rejected_before_file_operations(self):
  row={'version':2,'body':{'files':{}}}
  with patch.object(api.store,'get',AsyncMock(return_value=row)),patch.object(api.store,'update',AsyncMock()) as update:
   with self.assertRaises(HTTPException) as caught:await api.change_files(uuid.uuid4(),api.FileOperations(version=1,operations=[{'op':'mkdir','path':'src'}]),SimpleNamespace(app=None),self.actor())
   self.assertEqual(caught.exception.status_code,409);update.assert_not_awaited()
 async def test_inference_keys_cannot_read_portal_projects(self):
  actor=self.actor();actor.key_id=uuid.uuid4()
  with patch.object(api.store,'get',AsyncMock()) as get:
   with self.assertRaises(HTTPException):await api.project_files(uuid.uuid4(),SimpleNamespace(app=None),actor)
   get.assert_not_awaited()
 async def test_owner_check_precedes_restore_version_query(self):
  with patch.object(api.store,'get',AsyncMock(side_effect=HTTPException(403,'resource_owner_required'))):
   with self.assertRaises(HTTPException):await api.restore_files(uuid.uuid4(),api.Restore(version=1,source_version=1),SimpleNamespace(app=None),self.actor())

if __name__=='__main__':unittest.main()
