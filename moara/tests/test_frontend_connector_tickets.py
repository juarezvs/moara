import asyncio,hashlib,hmac,json,uuid
from datetime import datetime,timezone
from types import SimpleNamespace
import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException,Request
from moara.gateway import connector_tickets as tickets

class Fixture:
    def __init__(self):
        identifier=uuid.uuid4()
        self.account={'id':identifier,'legacy_id':identifier,'subject':'webui:'+str(identifier),'active':True,'session_version':0}
        self.permissions={'chat.use','data.query','connectors.manage'};self.key_enabled=True;self.user_enabled=True;self.password_required=False
        self.regular_valid=True;self.replays=0;self.ticket=None;self.crypto=Fernet(Fernet.generate_key());self.binding={}
        self.config=SimpleNamespace(connector_key='internal-synthetic',forward_key='synthetic-forward',legacy_gateway='http://gateway',legacy_webui='http://webui',session_cookie='session',fernet=lambda:self.crypto)
    def actor(self,frontend=True):
        permissions=frozenset(self.permissions)
        def require(permission):
            if permission not in permissions:raise HTTPException(403,'denied')
        return SimpleNamespace(user_id=self.account['id'],subject=self.account['subject'],upstream_client_id='webui' if frontend else None,
            allowed_sources=None,password_change_required=self.password_required,require=require,can=lambda p:p in permissions)
    async def execute(self,query,params,**kwargs):
        if 'INSERT INTO moara.connector_tickets' in query:
            self.ticket={'account_id':uuid.UUID(params['account']),'auth_bundle':params['bundle'],'profile_id':params['profile'],'expires_at':params['expires']};self.token_hash=params['hash'];return
        if 'FROM moara.connector_tickets' in query:return self.ticket if params['hash']==self.token_hash else None
        if 'FROM moara.accounts' in query:return self.account
        raise AssertionError('Unexpected SQL')
    async def authenticate(self,request):
        self.replays+=1
        if not self.regular_valid:raise HTTPException(401,'expired_original_session')
        return self.actor(False)
    async def from_row(self,account,**kwargs):
        assert account is self.account and kwargs['upstream_client_id']=='webui'
        return self.actor()
    async def limit(self,*args):pass
    def upstream(self,request):
        if request.url.host=='gateway':return httpx.Response(200 if self.key_enabled else 401,json={'id':'webui','scopes':['chat']})
        assert request.url.path.endswith(str(self.account['legacy_id']))
        stamp=request.headers['x-moara-timestamp'];signature=hmac.new(self.config.forward_key.encode(),(stamp+':'+str(self.account['legacy_id'])).encode(),hashlib.sha256).hexdigest()
        assert hmac.compare_digest(signature,request.headers['x-moara-signature'])
        return httpx.Response(200,json={'enabled':self.user_enabled,**self.binding})
    def request(self,client,headers):
        app=SimpleNamespace(state=SimpleNamespace(settings=self.config,db=self,http=client,auth=self))
        return Request({'type':'http','method':'POST','path':'/v1/chat/completions','raw_path':b'/v1/chat/completions','root_path':'','scheme':'http','server':('test',80),
                        'client':('127.0.0.1',0),'headers':[(k.encode(),v.encode()) for k,v in headers.items()],'state':{'request_id':'synthetic'},'app':app})
    async def issued(self,client,frontend=True,secp=False):
        request=self.request(client,{'authorization':'Bearer synthetic-frontend-reserved-key','x-moara-verified-user':'short-hop-proof'})
        token=await tickets.issue(request,self.actor(frontend),'general',secp=secp)
        return self.request(client,{'authorization':'Bearer '+self.config.connector_key,'x-moara-execution-ticket':token})

def test_frontend_operation_does_not_replay_expired_assertion_and_roles_are_live():
    async def run():
        f=Fixture()
        async with httpx.AsyncClient(transport=httpx.MockTransport(f.upstream)) as client:
            request=await f.issued(client)
            bundle=json.loads(f.crypto.decrypt(f.ticket['auth_bundle'].encode()))
            assert bundle['_frontend_account_v1'] and 'short-hop-proof' not in json.dumps(bundle)
            assert 590<(f.ticket['expires_at']-datetime.now(timezone.utc)).total_seconds()<=600
            f.regular_valid=False # the short assertion can no longer authenticate a new request
            actor,_=await tickets.verified(request)
            assert actor.user_id==f.account['id'] and f.replays==0
            f.permissions.remove('connectors.manage')
            with pytest.raises(HTTPException) as error:
                await tickets.authorize_query(tickets.Permission(source_id=uuid.uuid4(),purpose='personnel'),request)
            assert error.value.status_code==403
    asyncio.run(run())

@pytest.mark.parametrize('revocation',['key','user','account','version','subject','password'])
def test_frontend_operation_fails_closed_after_revocation(revocation):
    async def run():
        f=Fixture()
        async with httpx.AsyncClient(transport=httpx.MockTransport(f.upstream)) as client:
            request=await f.issued(client)
            if revocation=='key':f.key_enabled=False
            if revocation=='user':f.user_enabled=False
            if revocation=='account':f.account['active']=False
            if revocation=='version':f.account['session_version']+=1
            if revocation=='subject':f.account['subject']='webui:'+str(uuid.uuid4())
            if revocation=='password':f.password_required=True
            with pytest.raises(HTTPException):await tickets.verified(request)
    asyncio.run(run())

def test_regular_credentials_are_still_reauthenticated_and_frontend_needs_signed_hop():
    async def run():
        f=Fixture()
        async with httpx.AsyncClient(transport=httpx.MockTransport(f.upstream)) as client:
            request=await f.issued(client,False);f.regular_valid=False
            with pytest.raises(HTTPException):await tickets.verified(request)
            assert f.replays==1
            request=f.request(client,{'authorization':'Bearer synthetic-frontend-reserved-key'})
            with pytest.raises(HTTPException):await tickets.issue(request,f.actor(),'general')
    asyncio.run(run())

def test_moara_admin_does_not_replace_verified_institutional_identity_for_secp():
    async def run():
        f=Fixture()
        async with httpx.AsyncClient(transport=httpx.MockTransport(f.upstream)) as client:
            request=await f.issued(client,secp=True)
            with pytest.raises(HTTPException) as error:await tickets.secp_identity(request)
            assert error.value.status_code==403
            f.binding={'institutional_verified':True,'username':'MAT001','organization':'SJAM','directory_object_id':str(uuid.uuid4()),'directory_fingerprint':'f'*64}
            f.account['preferences']={'secp_profile':'SERVIDOR'}
            result=await tickets.secp_identity(request)
            assert result['identity']['username']=='MAT001' and result['identity']['profile']=='SERVIDOR'
            f.permissions.discard('data.query');f.permissions.discard('connectors.manage')
            result=await tickets.authorize_query(tickets.Permission(source_id=uuid.uuid4(),purpose='secp'),request)
            assert result['authorized'] and result['identity']['organization']=='SJAM'
            with pytest.raises(HTTPException):await tickets.authorize_query(tickets.Permission(source_id=uuid.uuid4(),purpose='query'),request)
    asyncio.run(run())

@pytest.mark.parametrize('invalid',[
    {'username':'typed@example.org'}, {'directory_object_id':'not-a-guid'}, {'organization':''}, {'institutional_verified':False}, {'enabled':False}, {'directory_fingerprint':'untrusted'},
])
def test_institutional_binding_is_not_inferred_from_email_or_untrusted_fields(invalid):
    async def run():
        f=Fixture();f.account['email']='MAT001@example.org'
        f.binding={'institutional_verified':True,'username':'MAT001','organization':'SJAM','directory_object_id':str(uuid.uuid4()),'directory_fingerprint':'f'*64,**invalid}
        async with httpx.AsyncClient(transport=httpx.MockTransport(f.upstream)) as client:
            request=await f.issued(client,secp=True)
            with pytest.raises(HTTPException):await tickets.secp_identity(request)
    asyncio.run(run())
