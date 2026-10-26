"""Own sessions/RBAC with an explicit, verified legacy-auth transition adapter."""
import asyncio
import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import datetime,timedelta,timezone

import httpx
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError,InvalidHashError
from fastapi import HTTPException,Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from .database import as_json
from .rbac import Actor,ROLES

PASSWORDS=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2)
PASSWORD_SLOTS=asyncio.Semaphore(4)
DUMMY_HASH=PASSWORDS.hash('moara-non-user-dummy-password')
LIMIT_SCRIPT="local n=redis.call('INCR',KEYS[1]);if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]);end;return n"

def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def now():return datetime.now(timezone.utc)

class Auth:
    def __init__(self,settings,db,http):
        self.settings=settings;self.db=db;self.http=http;self.crypto=settings.fernet()
        self.redis=Redis.from_url(settings.redis_url(),decode_responses=True,max_connections=20,socket_timeout=3,socket_connect_timeout=3)

    async def seed_roles(self):
        for key,(name,permissions) in ROLES.items():
            await self.db.execute('''INSERT INTO moara.roles(id,name,permissions,builtin) VALUES(:id,:name,CAST(:permissions AS jsonb),true)
                ON CONFLICT(id) DO NOTHING''',{'id':key,'name':name,'permissions':as_json(sorted(permissions))})

    async def limit(self,bucket,count=120,seconds=60):
        try:n=await self.redis.eval(LIMIT_SCRIPT,1,'moara:limit:'+digest(bucket),seconds)
        except RedisError:raise HTTPException(503,'rate_limiter_unavailable') from None
        if int(n)>count:raise HTTPException(429,'rate_limit_exceeded',headers={'Retry-After':str(seconds)})

    async def upsert_legacy(self,data):
        try:
            legacy_id=uuid.UUID(str(data['id']));role=data['role']
            if role not in ('user','admin'):raise ValueError()
            name=str(data.get('name') or 'Conta institucional')[:160];email=str(data.get('email') or '')[:200]
        except (KeyError,ValueError,TypeError):raise HTTPException(403,'legacy_identity_not_authorized') from None
        subject='webui:'+str(legacy_id)
        async with self.db.engine.begin() as conn:
            created=await self.db.execute('''INSERT INTO moara.accounts(id,subject,name,email,auth_source,legacy_id)
                VALUES(CAST(:id AS uuid),:subject,:name,:email,'legacy',CAST(:id AS uuid)) ON CONFLICT(subject) DO NOTHING RETURNING id''',
                {'id':str(legacy_id),'subject':subject,'name':name,'email':email},one=True,conn=conn)
            if created:
                await self.db.execute('INSERT INTO moara.account_roles(account_id,role_id) VALUES(CAST(:id AS uuid),:role)',
                    {'id':str(legacy_id),'role':'administrator' if role=='admin' else 'user'},conn=conn)
            await self.db.execute('UPDATE moara.accounts SET name=:name,email=:email,updated_at=now() WHERE subject=:subject',
                {'name':name,'email':email,'subject':subject},conn=conn)
            row=await self.db.execute('SELECT * FROM moara.accounts WHERE subject=:subject',{'subject':subject},one=True,conn=conn)
        if not row['active']:raise HTTPException(403,'account_disabled')
        return row

    async def legacy_user(self,token):
        try:
            response=await self.http.get(self.settings.legacy_webui+'/api/v1/auths/',headers={'Authorization':'Bearer '+token},timeout=10)
        except httpx.HTTPError:raise HTTPException(503,'legacy_auth_unavailable') from None
        if response.status_code!=200:raise HTTPException(401,'session_expired')
        return await self.upsert_legacy(response.json())

    async def from_row(self,row,**kwargs):
        if not row or not row['active']:raise HTTPException(403,'account_disabled')
        if self.settings.directory_enforcement and row['subject'].startswith('webui:'):
            identifier=str(row['id']);stamp=str(int(time.time()))
            signature=hmac.new(self.settings.forward_key.encode(),(stamp+':'+identifier).encode(),hashlib.sha256).hexdigest()
            try:
                result=await self.http.get(self.settings.legacy_webui+'/api/v1/moara/internal/identity/'+identifier,
                    headers={'X-Moara-Timestamp':stamp,'X-Moara-Signature':signature},timeout=5)
            except httpx.HTTPError:raise HTTPException(503,'institutional_directory_unavailable') from None
            if result.status_code!=200:raise HTTPException(503,'institutional_directory_unavailable')
            identity=result.json()
            if identity.get('enabled') is not True:raise HTTPException(403,'institutional_unit_disabled')
            if identity.get('institutional_verified') is False:raise HTTPException(403,'directory_binding_changed')
            if identity.get('organization'):
                group_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'moara:organization:'+identity['organization']))
                # Membership comes only from the server-side immutable AD binding.
                async with self.db.engine.begin() as conn:
                    await self.db.execute('SELECT id FROM moara.accounts WHERE id=CAST(:id AS uuid) FOR UPDATE',{'id':identifier},conn=conn)
                    created=await self.db.execute('''INSERT INTO moara.groups(id,name) VALUES(CAST(:id AS uuid),:name)
                        ON CONFLICT DO NOTHING RETURNING id''',{'id':group_id,'name':'org:'+identity['organization']},one=True,conn=conn)
                    if created:
                        await self.db.execute('''UPDATE moara.profiles SET allowed_groups=allowed_groups || CAST(:item AS jsonb)
                            WHERE id IN ('fast','coding','general','gemma4-12b') AND NOT allowed_groups @> CAST(:item AS jsonb)''',
                            {'item':as_json([group_id])},conn=conn)
                        await self.db.audit(None,'organization.chat_group.created',identity['organization'],conn=conn)
                    await self.db.execute('''DELETE FROM moara.group_members m USING moara.groups g
                        WHERE m.group_id=g.id AND m.account_id=CAST(:id AS uuid) AND g.name LIKE 'org:%' AND g.id<>CAST(:group AS uuid)''',
                        {'id':identifier,'group':group_id},conn=conn)
                    await self.db.execute('''INSERT INTO moara.group_members(group_id,account_id)
                        SELECT id,CAST(:id AS uuid) FROM moara.groups WHERE id=CAST(:group AS uuid) ON CONFLICT DO NOTHING''',
                        {'id':identifier,'group':group_id},conn=conn)
        roles=await self.db.execute('''SELECT r.id,r.permissions FROM moara.roles r JOIN moara.account_roles a ON a.role_id=r.id
            WHERE a.account_id=CAST(:id AS uuid)''',{'id':str(row['id'])})
        permissions=frozenset(p for r in roles for p in r['permissions'])
        return Actor(user_id=row['id'],subject=row['subject'],name=row['name'],email=row['email'],
            roles=tuple(r['id'] for r in roles),permissions=permissions,auth_source=row['auth_source'],
            password_change_required=row['password_change_required'],preferences=row.get('preferences') or {},**kwargs)

    async def session(self,row,legacy_token=None):
        identifier=uuid.uuid4();token=secrets.token_urlsafe(48);expires=now()+timedelta(seconds=self.settings.session_seconds)
        if legacy_token:
            # Claims are used only to shorten lifetime; identity was verified by the legacy server.
            try:
                payload=jwt.decode(legacy_token,options={'verify_signature':False})
                if isinstance(payload.get('exp'),(int,float)):expires=min(expires,datetime.fromtimestamp(payload['exp'],timezone.utc))
            except (ValueError,jwt.PyJWTError):raise HTTPException(401,'invalid_legacy_session') from None
        await self.db.execute('''INSERT INTO moara.sessions(id,account_id,token_hash,session_version,legacy_token,legacy_checked_at,expires_at)
            VALUES(CAST(:id AS uuid),CAST(:account AS uuid),:hash,:version,:legacy,now(),:expires)''',
            {'id':str(identifier),'account':str(row['id']),'hash':digest(token),'version':row['session_version'],
                'legacy':self.crypto.encrypt(legacy_token.encode()).decode() if legacy_token else None,'expires':expires})
        return token,expires

    async def password_login(self,email,password,client_ip):
        # SSH tunnels and the reverse proxy may legitimately share one IP.
        # The separate per-account bound still limits credential guessing.
        await self.limit('login-ip:'+client_ip,60,300)
        await self.limit('login-email:'+email.casefold(),8,300)
        local=await self.db.execute("SELECT * FROM moara.accounts WHERE auth_source='local' AND lower(email)=:email",{'email':email.casefold()},one=True)
        if local:
            async with PASSWORD_SLOTS:
                def verify():
                    try:return PASSWORDS.verify(local['password_hash'] or DUMMY_HASH,password)
                    except (VerificationError,InvalidHashError):return False
                valid=await asyncio.to_thread(verify)
            if not valid or not local['active']:raise HTTPException(401,'invalid_credentials')
            return local,None
        try:
            response=await self.http.post(self.settings.legacy_webui+'/api/v1/auths/signin',json={'email':email,'password':password},timeout=15)
        except httpx.HTTPError:raise HTTPException(503,'legacy_auth_unavailable') from None
        if response.status_code!=200:raise HTTPException(401,'invalid_credentials')
        data=response.json()
        if not isinstance(data,dict) or not isinstance(data.get('token'),str):
            # MFA challenges are completed by the existing authentication UI.
            raise HTTPException(409,'complete_institutional_login_in_existing_chat')
        token=data['token']
        row=await self.legacy_user(token)
        return row,token

    def origin(self,request):
        origin=request.headers.get('origin')
        if origin and origin not in self.settings.origins:raise HTTPException(403,'origin_not_allowed')

    async def authenticate(self,request:Request):
        rate=240
        authorization=request.headers.get('authorization','')
        cookie=request.cookies.get(self.settings.session_cookie)
        if authorization:
            if not authorization.startswith('Bearer '):raise HTTPException(401,'authentication_required')
            token=authorization[7:]
            if not 16<=len(token)<=4096:raise HTTPException(401,'authentication_required')
            if token.startswith('moara_'):
                key=await self.db.execute('''SELECT k.*,a.active,a.subject,a.name AS account_name,a.email,a.auth_source,a.password_change_required
                    FROM moara.api_keys k JOIN moara.accounts a ON a.id=k.account_id
                    WHERE k.token_hash=:hash AND k.revoked_at IS NULL AND (k.expires_at IS NULL OR k.expires_at>now())''',{'hash':digest(token)},one=True)
                if not key:raise HTTPException(401,'invalid_api_key')
                row=await self.db.execute('SELECT * FROM moara.accounts WHERE id=CAST(:id AS uuid)',{'id':str(key['account_id'])},one=True)
                actor=await self.from_row(row,key_id=key['id'],allowed_profiles=tuple(key['allowed_profiles']),allowed_sources=tuple(key['allowed_sources']))
                actor.permissions=frozenset(p for p in key['scopes'] if actor.can(p))
                rate=key['rpm']
                await self.db.execute('UPDATE moara.api_keys SET last_used_at=now() WHERE id=CAST(:id AS uuid)',{'id':str(key['id'])})
            elif token.count('.')==2:
                actor=await self.from_row(await self.legacy_user(token),legacy_token=token)
            else:
                try:response=await self.http.get(self.settings.legacy_gateway+'/v1/auth/identity',headers={'Authorization':'Bearer '+token},timeout=10)
                except httpx.HTTPError:raise HTTPException(503,'integration_auth_unavailable') from None
                if response.status_code!=200:raise HTTPException(401,'invalid_api_key')
                identity=response.json();client_id=str(identity.get('id',''))
                if not re_identifier(client_id):raise HTTPException(401,'invalid_api_key')
                forwarded=request.headers.get('x-moara-verified-user') or request.headers.get('x-openwebui-user-jwt')
                # The reserved frontend key can list public compatibility profiles
                # during its background refresh, but cannot infer as a shared user.
                if client_id=='webui' and not forwarded and request.method!='GET':
                    raise HTTPException(401,'signed_frontend_identity_required')
                if client_id=='webui' and forwarded:
                    try:
                        data=jwt.decode(forwarded,self.settings.forward_key,algorithms=['HS256'],issuer='open-webui',
                            options={'require':['sub','iss','iat','exp'],'verify_aud':False},leeway=5)
                        if data['exp']-data['iat']>120:raise ValueError()
                    except (jwt.PyJWTError,ValueError,KeyError,TypeError):raise HTTPException(401,'invalid_forwarded_identity') from None
                    actor=await self.from_row(await self.upsert_legacy({**data,'id':data['sub']}),upstream_key=token,upstream_client_id=client_id)
                else:
                    subject='key:'+client_id;identifier=uuid.uuid5(uuid.NAMESPACE_URL,'moara:'+subject)
                    row=await self.db.execute('''INSERT INTO moara.accounts(id,subject,name,auth_source) VALUES(CAST(:id AS uuid),:subject,:name,'integration')
                        ON CONFLICT(subject) DO UPDATE SET subject=EXCLUDED.subject RETURNING *''',{'id':str(identifier),'subject':subject,'name':client_id},one=True)
                    scopes=set(identity.get('scopes',[]));permissions=set()
                    if 'chat' in scopes:permissions|={'chat.use','profiles.read','identity.read'}
                    if client_id=='admin' and {'chat','metrics','ingest'}<=scopes:permissions={'*'}
                    actor=Actor(row['id'],subject,client_id,None,('legacy_integration',),frozenset(permissions),auth_source='integration',upstream_key=token,upstream_client_id=client_id)
                    if not row['active']:raise HTTPException(403,'account_disabled')
        elif cookie:
            if len(cookie)>128:raise HTTPException(401,'session_expired')
            session=await self.db.execute('''SELECT s.*,a.active,a.session_version AS account_version FROM moara.sessions s
                JOIN moara.accounts a ON a.id=s.account_id WHERE s.token_hash=:hash AND s.revoked_at IS NULL AND s.expires_at>now()''',{'hash':digest(cookie)},one=True)
            if not session or not session['active'] or session['session_version']!=session['account_version']:raise HTTPException(401,'session_expired')
            expected=hmac.new(self.settings.session_key,cookie.encode(),hashlib.sha256).hexdigest()
            if request.method not in ('GET','HEAD','OPTIONS'):
                self.origin(request)
                if not hmac.compare_digest(request.headers.get('x-moara-csrf',''),expected):raise HTTPException(403,'csrf_required')
            legacy=None
            if session['legacy_token']:
                try:legacy=self.crypto.decrypt(session['legacy_token'].encode()).decode()
                except Exception:raise HTTPException(401,'session_expired') from None
                checked=session['legacy_checked_at']
                if checked is None or (now()-checked).total_seconds()>60:
                    try:await self.legacy_user(legacy)
                    except HTTPException as exc:
                        if exc.status_code in (401,403):
                            await self.db.execute('UPDATE moara.sessions SET revoked_at=now() WHERE id=CAST(:id AS uuid)',{'id':str(session['id'])})
                        raise
                    await self.db.execute('UPDATE moara.sessions SET legacy_checked_at=now() WHERE id=CAST(:id AS uuid)',{'id':str(session['id'])})
            row=await self.db.execute('SELECT * FROM moara.accounts WHERE id=CAST(:id AS uuid)',{'id':str(session['account_id'])},one=True)
            actor=await self.from_row(row,session_id=session['id'],csrf=expected,legacy_token=legacy)
        else:raise HTTPException(401,'authentication_required')
        route=getattr(request.scope.get('route'),'path',request.url.path)
        if actor.password_change_required and actor.key_id is None and route not in ('/api/v1/auth/me','/api/v1/auth/password','/api/v1/auth/logout'):
            raise HTTPException(403,'password_change_required')
        await self.limit('actor:'+actor.subject+(':'+str(actor.key_id) if actor.key_id else ''),rate,60)
        request.state.actor=actor
        return actor

    async def close(self):await self.redis.aclose()

def re_identifier(value):
    import re
    return bool(re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',value))

async def current_actor(request:Request):return await request.app.state.auth.authenticate(request)

def require(permission):
    async def dependency(request:Request):
        actor=await current_actor(request);actor.require(permission);return actor
    return dependency
