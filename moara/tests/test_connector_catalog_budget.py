import asyncio
from types import SimpleNamespace
import httpx
import pytest
from fastapi import HTTPException,Request
from moara.gateway.connectors_api import proxy

@pytest.mark.parametrize('path,admin,size,allowed',[
    ('sources',True,4*1024**2+128,True),
    ('sources',False,4*1024**2+128,False),
    ('audit',True,4*1024**2+128,False),
    ('sources',True,16*1024**2+128,False),
])
def test_large_catalog_is_only_allowed_for_the_bounded_administrative_registry(path,admin,size,allowed):
    async def run():
        async def audit(*args,**kwargs):pass
        async def receive():return {'type':'http.request','body':b'','more_body':False}
        actor=SimpleNamespace(subject='local:synthetic',allowed_sources=None,require=lambda permission:None,
                              can=lambda permission:admin if permission=='connectors.manage' else True)
        content=b'["'+b'x'*size+b'"]'
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=content))) as client:
            app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(connector_key='synthetic',connector_hub='http://hub'),http=client,db=SimpleNamespace(audit=audit)))
            request=Request({'type':'http','method':'GET','path':'/api/v1/connectors/'+path,'headers':[],'app':app,'state':{'request_id':'synthetic'}},receive)
            if allowed:
                result=await proxy(path,request,actor)
                assert result.status_code==200 and result.body==content
            else:
                with pytest.raises(HTTPException) as error:await proxy(path,request,actor)
                assert error.value.status_code==502
    asyncio.run(run())
