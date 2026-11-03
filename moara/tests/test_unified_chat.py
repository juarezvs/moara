import uuid,unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from contextlib import asynccontextmanager
from datetime import datetime,timezone
import httpx
from fastapi import HTTPException
from cryptography.fernet import Fernet
from moara.gateway import previous_history as previous,auth_api
from moara.gateway.auth import Auth
from moara.gateway.rbac import Actor

def actor():return Actor(uuid.uuid4(),'webui:'+str(uuid.uuid4()),'Synthetic',None,(),frozenset({'history.read','history.manage'}),legacy_token='SYNTHETIC_UPSTREAM_TOKEN')
def request(http=None,auth=None):return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(http=http,auth=auth,settings=SimpleNamespace(legacy_webui='http://legacy'))),client=SimpleNamespace(host='test'),state=SimpleNamespace(request_id=uuid.uuid4()))

class PreviousHistoryTests(unittest.IsolatedAsyncioTestCase):
 def test_only_selected_branch_is_copied(self):
  messages={'u':{'role':'user','content':'Question','parentId':None},'a':{'role':'assistant','content':'Selected answer','parentId':'u'},'sibling':{'role':'assistant','content':'Other version','parentId':'u'}}
  result=previous.branch({'history':{'currentId':'a','messages':messages}})
  self.assertEqual([m['content'] for m in result],['Question','Selected answer'])
 def test_cycles_and_missing_parents_cannot_silently_change_history(self):
  for mapping in [{'a':{'parentId':'a'}},{'a':{'parentId':'missing'}}]:
   with self.assertRaises(HTTPException):previous.branch({'history':{'currentId':'a','messages':mapping}})
 async def test_admin_cannot_view_another_owners_conversation(self):
  identifier=uuid.uuid4();a=actor();http=SimpleNamespace(get=AsyncMock(return_value=httpx.Response(200,json={'id':str(identifier),'user_id':str(uuid.uuid4()),'chat':{}},request=httpx.Request('GET','http://legacy'))))
  with self.assertRaises(HTTPException) as e:await previous.read(identifier,request(http),a)
  self.assertEqual(e.exception.status_code,404)
 async def test_api_key_cannot_read_previous_chat_even_with_management_scope(self):
  a=actor();a.key_id=uuid.uuid4()
  with self.assertRaises(HTTPException) as e:await previous.read(uuid.uuid4(),request(),a)
  self.assertEqual(e.exception.status_code,403)
 async def test_copy_is_encrypted_ordered_and_does_not_mutate_original(self):
  a=actor();identifier=uuid.uuid4();payload={'id':str(identifier),'user_id':a.subject.removeprefix('webui:'),'title':'Synthetic previous chat','chat':{'messages':[{'role':'user','content':'Synthetic question'},{'role':'assistant','content':'Synthetic answer'}]}}
  http=SimpleNamespace(get=AsyncMock(return_value=httpx.Response(200,json=payload,request=httpx.Request('GET','http://legacy'))))
  @asynccontextmanager
  async def begin():yield object()
  crypto=Fernet(Fernet.generate_key());db=SimpleNamespace(execute=AsyncMock(return_value={'id':str(uuid.uuid4()),'title':'Synthetic','profile_id':'auto','updated_at':datetime.now(timezone.utc)}),audit=AsyncMock(),engine=SimpleNamespace(begin=begin))
  r=request(http);r.app.state.db=db;r.app.state.settings.fernet=lambda:crypto
  result=await previous.resume(identifier,r,a)
  messages=[call.args[1] for call in db.execute.await_args_list if 'INSERT INTO moara.messages' in call.args[0]]
  self.assertEqual([crypto.decrypt(m['content'].encode()).decode() for m in messages],['Synthetic question','Synthetic answer'])
  self.assertLess(messages[0]['created'],messages[1]['created']);self.assertEqual(http.get.await_count,1)
  self.assertFalse(any('DELETE' in call.args[0] for call in db.execute.await_args_list));self.assertIn('Anexos',result['notice'])

class UnifiedAuthenticationTests(unittest.IsolatedAsyncioTestCase):
 def auth(self,data):
  value=Auth.__new__(Auth);value.limit=AsyncMock();value.db=SimpleNamespace(execute=AsyncMock(return_value=None));value.settings=SimpleNamespace(legacy_webui='http://legacy')
  value.http=SimpleNamespace(post=AsyncMock(return_value=httpx.Response(200,json=data,request=httpx.Request('POST','http://legacy'))));value.legacy_user=AsyncMock(return_value={'id':'synthetic'})
  return value
 async def test_directory_login_uses_existing_authority_and_never_links_by_email(self):
  a=self.auth({'token':'SYNTHETIC_SESSION_TOKEN'});await a.password_login('realm\\user','SYNTHETIC_PASSWORD','test')
  self.assertTrue(a.http.post.await_args.args[0].endswith('/auths/ldap'));self.assertEqual(a.http.post.await_args.kwargs['json']['user'],'realm\\user')
 async def test_mfa_challenge_cannot_create_authenticated_session(self):
  a=self.auth({'next_step':'verify','challenge_token':'X'*32,'expires_in':300})
  row,challenge=await a.password_login('person@example.test','SYNTHETIC_PASSWORD','test')
  self.assertIsNone(row);self.assertTrue(challenge['mfa_required']);a.legacy_user.assert_not_called()
  a.origin=lambda r:None;a.session=AsyncMock();r=request(auth=a)
  a.password_login=AsyncMock(return_value=(None,challenge))
  response=await auth_api.login(auth_api.Login(email='person@example.test',password='SYNTHETIC_PASSWORD'),r)
  self.assertNotIn('set-cookie',response.headers);a.session.assert_not_called();self.assertEqual(response.headers['cache-control'],'no-store')
 async def test_bad_second_factor_never_creates_session(self):
  a=self.auth({});a.origin=lambda r:None;a.session=AsyncMock();r=request(a.http,a)
  a.http.post.return_value=httpx.Response(401,json={'detail':'bad code'},request=httpx.Request('POST','http://legacy'))
  with self.assertRaises(HTTPException):await auth_api.mfa('verify',auth_api.Mfa(challenge_token='X'*32,code='000000'),r)
  a.session.assert_not_called();a.legacy_user.assert_not_called()
