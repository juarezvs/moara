import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException
from starlette.requests import Request
from pydantic import ValidationError
from moara.gateway.auth import Auth
from moara.gateway.rbac import Actor
from moara.gateway.admin_api import KeyCreate
from moara.gateway.developer_api import PersonalKey


class UnlimitedKeyTests(unittest.IsolatedAsyncioTestCase):
    def fixture(self, rpm=0, valid=True):
        key_id, owner = uuid.uuid4(), uuid.uuid4()
        key = dict(id=key_id, account_id=owner, allowed_profiles=['general'],
                   allowed_sources=[], scopes=['chat.use'], rpm=rpm)
        auth = Auth.__new__(Auth)
        auth.settings = SimpleNamespace(session_cookie='session')
        auth.db = SimpleNamespace(execute=AsyncMock(side_effect=[key if valid else None, {}, None]))
        auth.from_row = AsyncMock(return_value=Actor(owner, 'test:owner', 'Test', None,
                                                   (), frozenset({'chat.use'}), key_id=key_id))
        auth.limit = AsyncMock()
        request = Request({'type': 'http', 'method': 'POST', 'path': '/moara/v1/chat/completions',
                           'headers': [(b'authorization', b'Bearer moara_synthetic_test_key')],
                           'scheme': 'https', 'server': ('test', 443), 'query_string': b''})
        return auth, request

    async def test_explicit_zero_quota_skips_only_request_counter(self):
        auth, request = self.fixture()
        actor = await auth.authenticate(request)
        auth.limit.assert_not_awaited()
        auth.from_row.assert_awaited_once()
        self.assertEqual(actor.permissions, frozenset({'chat.use'}))
        self.assertIs(request.state.actor, actor)

    async def test_positive_quota_is_still_enforced(self):
        auth, request = self.fixture(rpm=20)
        await auth.authenticate(request)
        self.assertEqual(auth.limit.await_args.args[1:], (20, 60))

    async def test_zero_never_makes_an_invalid_key_valid(self):
        auth, request = self.fixture(valid=False)
        with self.assertRaises(HTTPException) as error:
            await auth.authenticate(request)
        self.assertEqual(error.exception.status_code, 401)
        auth.from_row.assert_not_awaited()

    def test_only_administrative_issuance_accepts_zero(self):
        key = KeyCreate(account_id=uuid.uuid4(), name='IDE', scopes=['chat.use'],
                        allowed_profiles=['general'], rpm=0)
        self.assertEqual(key.rpm, 0)
        with self.assertRaises(ValidationError):
            PersonalKey(name='IDE', rpm=0)
        with self.assertRaises(ValidationError):
            KeyCreate(account_id=uuid.uuid4(), name='IDE', scopes=['chat.use'],
                      allowed_profiles=['general'], rpm=-1)
