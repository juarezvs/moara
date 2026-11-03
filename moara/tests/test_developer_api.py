import unittest,uuid,json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from pydantic import ValidationError
from fastapi import HTTPException
from moara.gateway.rbac import Actor
from moara.gateway import developer_api as api,ide_compat,catalog_api
from moara.gateway.auth import digest
from moara.gateway.chat_api import Completion

def actor():return Actor(uuid.uuid4(),'test:ide','Synthetic developer',None,('user',),frozenset(api.SCOPES),session_id=uuid.uuid4())
class Engine:
 @asynccontextmanager
 async def begin(self):yield object()

class KeyTests(unittest.IsolatedAsyncioTestCase):
 def request(self,count=0,revoke_found=True):
  async def execute(sql,params=None,**kwargs):
   if 'FOR UPDATE' in sql:return {'id':params['owner'],'active':True}
   if 'count(*)' in sql:return {'count':count}
   if 'UPDATE moara.api_keys' in sql:return {'id':params['id']} if revoke_found else None
   return []
  db=SimpleNamespace(engine=Engine(),execute=AsyncMock(side_effect=execute),audit=AsyncMock())
  return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db=db)),state=SimpleNamespace(request_id=uuid.uuid4()))

 async def test_issuance_is_owner_only_hash_only_and_inference_only(self):
  a=actor();r=self.request()
  with patch.object(api,'principal',AsyncMock(return_value=({'id':'general'},[{'capabilities':{'completion':True}}]))):
   value=await api.create_key(api.PersonalKey(name='IDE test'),r,a)
  inserts=[call for call in r.app.state.db.execute.await_args_list if 'INSERT INTO moara.api_keys' in call.args[0]]
  self.assertEqual(len(inserts),1);params=inserts[0].args[1]
  self.assertEqual(params['owner'],str(a.user_id));self.assertEqual(params['hash'],digest(value['token']))
  self.assertNotIn(value['token'],json.dumps(params,default=str));self.assertTrue(value['display_once'])
  self.assertEqual(json.loads(params['profiles']),['general']);self.assertEqual(set(json.loads(params['scopes'])),set(api.SCOPES))
  self.assertTrue(any('FOR UPDATE' in call.args[0] for call in r.app.state.db.execute.await_args_list))

 async def test_active_key_limit_prevents_insert(self):
  r=self.request(count=api.MAX_ACTIVE_KEYS)
  with patch.object(api,'principal',AsyncMock(return_value=({},[{'capabilities':{'completion':True}}]))):
   with self.assertRaises(HTTPException) as exc:await api.create_key(api.PersonalKey(name='IDE test'),r,actor())
  self.assertEqual(exc.exception.status_code,409)
  self.assertFalse(any('INSERT INTO moara.api_keys' in call.args[0] for call in r.app.state.db.execute.await_args_list))

 async def test_revoke_is_constrained_to_current_owner(self):
  r=self.request(revoke_found=False);a=actor()
  with self.assertRaises(HTTPException) as exc:await api.revoke(uuid.uuid4(),r,a)
  self.assertEqual(exc.exception.status_code,404)
  query=r.app.state.db.execute.await_args
  self.assertIn('account_id=CAST(:owner AS uuid)',query.args[0]);self.assertEqual(query.args[1]['owner'],str(a.user_id))
  r.app.state.db.audit.assert_not_awaited()

 async def test_key_listing_does_not_select_hash_or_secret(self):
  r=self.request();await api.keys(r,actor());sql=r.app.state.db.execute.await_args.args[0]
  self.assertNotIn('token_hash',sql);self.assertIn('account_id=CAST(:owner AS uuid)',sql)

 async def test_owner_admin_model_access_is_intersected_with_key_profile_list(self):
  a=actor();a.session_id=None;a.key_id=uuid.uuid4();a.allowed_profiles=('general',);a.owner_profiles_manage=True
  rows=[{'id':name,'public':False,'allowed_subjects':[],'allowed_groups':[]} for name in ['general','coding']]
  db=SimpleNamespace(execute=AsyncMock(side_effect=[rows,[]]))
  result=await catalog_api.visible_profiles(db,a)
  self.assertEqual([v['id'] for v in result],['general']);self.assertFalse(a.can('profiles.manage'))
  a.owner_profiles_manage=False;db.execute=AsyncMock(side_effect=[rows,[]])
  self.assertEqual(await catalog_api.visible_profiles(db,a),[])

class ContractTests(unittest.TestCase):
 def test_api_keys_and_bearer_sessions_cannot_mint_or_manage_personal_keys(self):
  for kind in ['key','bearer','integration']:
   a=actor()
   if kind=='key':a.key_id=uuid.uuid4()
   if kind=='bearer':a.session_id=None
   if kind=='integration':a.auth_source='integration'
   with self.assertRaises(HTTPException):api.interactive(a)

 def test_personal_key_request_rejects_scope_owner_or_rate_escalation(self):
  for extra in [{'account_id':str(uuid.uuid4())},{'scopes':['*']},{'rpm':601},{'validity_days':366},{'name':'  '}]:
   with self.assertRaises(ValidationError):api.PersonalKey.model_validate({'name':'IDE test',**extra})

 def test_alias_forces_authorized_shared_profile_and_developer_assistant(self):
  value=ide_compat.prepare(Completion(model='moara-code',messages=[{'role':'user','content':'Write Python code'}]),actor())
  self.assertEqual(value.model,'general');self.assertEqual(value.assistant_id,'desenvolvedora')
  a=actor();a.permissions=frozenset({'chat.use'})
  with self.assertRaises(HTTPException):ide_compat.prepare(Completion(model='moara-code',messages=[{'role':'user','content':'Write code'}]),a)

 def test_text_parts_and_developer_role_are_normalized_without_trusting_documents(self):
  rows=ide_compat.normalize_messages([{'role':'developer','content':'Client instructions'},{'role':'user','content':[{'type':'text','text':'code'},{'type':'text','text':'context'}]}])
  self.assertEqual(rows[0]['role'],'system');self.assertEqual(rows[1]['content'],'code\ncontext')
  with self.assertRaises(HTTPException):ide_compat.normalize_messages([{'role':'user','content':[{'type':'image_url','image_url':{'url':'https://example.test'}}]}])

 def test_compatible_errors_and_config_have_no_external_paid_endpoint(self):
  body=ide_compat.error_body(401,'invalid_api_key');self.assertEqual(body['error']['type'],'authentication_error')
  config=api.continue_config(True)
  self.assertIn(api.BASE_URL,config);self.assertNotIn('api.openai.com',config)
  self.assertIn('${{ secrets.MOARA_API_KEY }}',config);self.assertIn('verifySsl: true',config)
  self.assertIn('tool_use',config);self.assertNotIn('tool_use',api.continue_config(False))

if __name__=='__main__':unittest.main()
