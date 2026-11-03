import unittest,uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock
from contextlib import asynccontextmanager
from fastapi import HTTPException
from moara.gateway.auth import Auth
from moara.gateway.rbac import ROLES,Actor
from moara.gateway import admin_api

@asynccontextmanager
async def begin():yield object()

class IdentityRbacTests(unittest.IsolatedAsyncioTestCase):
 def test_default_is_only_chat_and_own_history(self):
  self.assertEqual(ROLES['user'][1],{'chat.use','history.read','history.manage','profiles.read','identity.read'})
  self.assertFalse({'users.manage','development.use','data.query','workspace.use'} & ROLES['user'][1])
 async def test_new_upstream_admin_does_not_get_automatic_moara_admin(self):
  identifier=uuid.uuid4();row={'id':identifier,'active':True}
  db=SimpleNamespace(engine=SimpleNamespace(begin=begin),audit=AsyncMock(),execute=AsyncMock(side_effect=[{'id':identifier},None,None,row]))
  a=Auth.__new__(Auth);a.db=db
  self.assertEqual(await a.upsert_legacy({'id':str(identifier),'role':'admin','name':'Synthetic'}),row)
  grant=next(c for c in db.execute.await_args_list if 'INSERT INTO moara.account_roles' in c.args[0])
  self.assertEqual(grant.args[1]['role'],'user');db.audit.assert_awaited_once()
 async def test_existing_roles_are_not_reset_on_login(self):
  db=SimpleNamespace(engine=SimpleNamespace(begin=begin),audit=AsyncMock(),execute=AsyncMock(side_effect=[None,None,{'active':True}]))
  a=Auth.__new__(Auth);a.db=db
  await a.upsert_legacy({'id':str(uuid.uuid4()),'role':'user'})
  self.assertFalse(any('account_roles' in c.args[0] for c in db.execute.await_args_list))
 async def test_stale_stored_default_cannot_widen_permissions(self):
  a=Auth.__new__(Auth);a.settings=SimpleNamespace(directory_enforcement=False)
  a.db=SimpleNamespace(execute=AsyncMock(return_value=[{'id':'user','permissions':['*']}]))
  row={'id':uuid.uuid4(),'active':True,'subject':'local:fixture','name':'Fixture','email':None,'auth_source':'local','password_change_required':False}
  actor=await a.from_row(row)
  self.assertEqual(actor.permissions,frozenset(ROLES['user'][1]));self.assertFalse(actor.can('users.manage'))
 async def test_administrator_has_all_declared_permissions(self):
  from moara.gateway.rbac import PERMISSIONS
  a=Actor(uuid.uuid4(),'fixture','Fixture',None,('administrator',),frozenset(ROLES['administrator'][1]))
  self.assertTrue(all(a.can(p) for p in PERMISSIONS))
 def test_machine_credentials_cannot_change_roles(self):
  for key,source in [(uuid.uuid4(),'local'),(None,'integration')]:
   a=Actor(uuid.uuid4(),'fixture','Fixture',None,('administrator',),frozenset({'*'}),key_id=key,auth_source=source)
   with self.assertRaises(HTTPException):admin_api.interactive(a)

 async def test_default_chat_grants_only_shared_principal_and_honors_key_allowlist(self):
  from moara.gateway.catalog_api import visible_profiles
  a=Actor(uuid.uuid4(),'local:fixture','Fixture',None,('user',),frozenset(ROLES['user'][1]),auth_source='local')
  rows=[{'id':i,'public':False,'allowed_subjects':[],'allowed_groups':[]} for i in ['gemma4-12b','coding']]
  db=SimpleNamespace(execute=AsyncMock(side_effect=[rows,[]]))
  self.assertEqual([p['id'] for p in await visible_profiles(db,a)],['gemma4-12b'])
  a.key_id=uuid.uuid4();a.allowed_profiles=('coding',);db.execute=AsyncMock(side_effect=[rows,[]])
  self.assertEqual(await visible_profiles(db,a),[])
