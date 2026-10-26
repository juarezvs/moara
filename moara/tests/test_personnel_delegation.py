import asyncio
import uuid
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from moara.gateway import connector_tickets

def test_personnel_delegation_requires_live_administration_and_source_scope(monkeypatch):
    identifier=uuid.uuid4()
    class Actor:
        allowed_sources=None
        def __init__(self,permissions):self.permissions=permissions
        def require(self,p):
            if p not in self.permissions:raise HTTPException(403,'denied')
    async def run(permissions,purpose,restricted=False):
        actor=Actor(permissions)
        if restricted:actor.allowed_sources=()
        async def verified(request):return actor,{}
        monkeypatch.setattr(connector_tickets,'verified',verified)
        return await connector_tickets.authorize_query(connector_tickets.Permission(source_id=identifier,purpose=purpose),SimpleNamespace())
    assert asyncio.run(run({'data.query'},'query'))=={'authorized':True}
    assert asyncio.run(run({'data.query','connectors.manage'},'personnel'))=={'authorized':True}
    for permissions,restricted in (({'data.query'},False),({'connectors.manage'},False),({'data.query','connectors.manage'},True)):
        with pytest.raises(HTTPException):asyncio.run(run(permissions,'personnel',restricted))
