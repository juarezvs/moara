"""Opaque delegations with live credential/account/role checks per operation.

An authenticated frontend hop can start a bounded private operation. Its short
assertion is never reused as a long-running credential or accepted after expiry
on public authentication routes.
"""
import hmac
import json
import secrets
import uuid
import time
import hashlib
import httpx
from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from .auth import digest
from .database import as_json
from .chat_api import Completion,completion
router=APIRouter(prefix='/api/v1/internal/connectors',tags=['Internal delegated connector operations'])

async def issue(request,actor,profile=None,*,secp=False):
    token=secrets.token_urlsafe(48);headers={}
    if request.headers.get('authorization'):headers['authorization']=request.headers['authorization']
    elif request.cookies.get(request.app.state.settings.session_cookie):
        headers['cookie']=request.app.state.settings.session_cookie+'='+request.cookies[request.app.state.settings.session_cookie]
        headers['x-moara-csrf']=request.headers.get('x-moara-csrf','')
    else:raise HTTPException(401,'delegation_requires_authenticated_session')
    for name in ['x-moara-verified-user','x-openwebui-user-jwt','origin']:
        if request.headers.get(name):headers[name]=request.headers[name]
    frontend=getattr(actor,'upstream_client_id',None)=='webui';bundle=headers
    if frontend:
        if not actor.subject.startswith('webui:') or not any(headers.get(k) for k in ('x-moara-verified-user','x-openwebui-user-jwt')):
            raise HTTPException(401,'signed_frontend_identity_required')
        account=await request.app.state.db.execute('SELECT subject,session_version,active FROM moara.accounts WHERE id=CAST(:id AS uuid)',{'id':str(actor.user_id)},one=True)
        if not account or not account['active'] or account['subject']!=actor.subject:raise HTTPException(403,'delegation_identity_changed')
        bundle={'_frontend_account_v1':True,'authorization':headers['authorization'],'subject':actor.subject,'session_version':account['session_version']}
    if secp:bundle['_secp_operation']=True
    await request.app.state.db.execute('''INSERT INTO moara.connector_tickets(id,token_hash,account_id,auth_bundle,profile_id,expires_at)
        VALUES(CAST(:id AS uuid),:hash,CAST(:account AS uuid),:bundle,:profile,:expires)''',
        {'id':str(uuid.uuid4()),'hash':digest(token),'account':str(actor.user_id),
            'bundle':request.app.state.settings.fernet().encrypt(as_json(bundle).encode()).decode(),
            'profile':profile,'expires':datetime.now(timezone.utc)+timedelta(minutes=10 if frontend else 30)})
    return token

async def frontend_actor(request,row,bundle):
    config=request.app.state.settings;db=request.app.state.db;auth=request.app.state.auth
    account=await db.execute('SELECT * FROM moara.accounts WHERE id=CAST(:id AS uuid)',{'id':str(row['account_id'])},one=True)
    if not account or not account['active'] or account['subject']!=bundle.get('subject') or account['session_version']!=bundle.get('session_version'):
        raise HTTPException(403,'delegation_identity_changed')
    authorization=bundle.get('authorization','')
    if not isinstance(authorization,str) or not authorization.startswith('Bearer ') or not 16<=len(authorization[7:])<=4096:
        raise HTTPException(401,'execution_ticket_invalid')
    try:
        key=await request.app.state.http.get(config.legacy_gateway+'/v1/auth/identity',headers={'Authorization':authorization},timeout=10)
        identity=key.json() if key.status_code==200 else {}
    except (httpx.HTTPError,ValueError):raise HTTPException(503,'integration_auth_unavailable') from None
    if not isinstance(identity,dict) or identity.get('id')!='webui' or 'chat' not in identity.get('scopes',[]):raise HTTPException(401,'delegated_frontend_revoked')
    # Verify the actual user/unit even when directory enforcement is disabled.
    identifier=str(uuid.UUID(str(account.get('legacy_id') or account['id'])));stamp=str(int(time.time()))
    signature=hmac.new(config.forward_key.encode(),(stamp+':'+identifier).encode(),hashlib.sha256).hexdigest()
    try:
        user=await request.app.state.http.get(config.legacy_webui+'/api/v1/moara/internal/identity/'+identifier,
            headers={'X-Moara-Timestamp':stamp,'X-Moara-Signature':signature},timeout=5)
        enabled=user.json().get('enabled') if user.status_code==200 else False
    except (httpx.HTTPError,ValueError):raise HTTPException(503,'institutional_directory_unavailable') from None
    if enabled is not True:raise HTTPException(403,'institutional_identity_disabled')
    actor=await auth.from_row(account,upstream_key=authorization[7:],upstream_client_id='webui')
    if actor.password_change_required:raise HTTPException(403,'password_change_required')
    await auth.limit('actor:'+actor.subject,240,60)
    return actor

async def verified(request):
    config=request.app.state.settings
    if not hmac.compare_digest(request.headers.get('authorization',''),'Bearer '+config.connector_key):raise HTTPException(401,'internal_service_required')
    token=request.headers.get('x-moara-execution-ticket','')
    if not 32<=len(token)<=128:raise HTTPException(401,'execution_ticket_required')
    row=await request.app.state.db.execute('SELECT * FROM moara.connector_tickets WHERE token_hash=:hash AND expires_at>now()',{'hash':digest(token)},one=True)
    if not row:raise HTTPException(401,'execution_ticket_expired')
    try:headers=json.loads(config.fernet().decrypt(row['auth_bundle'].encode()))
    except Exception:raise HTTPException(401,'execution_ticket_invalid') from None
    if not isinstance(headers,dict):raise HTTPException(401,'execution_ticket_invalid')
    row['_secp_operation']=headers.pop('_secp_operation',False) is True
    if headers.get('_frontend_account_v1') is True:
        actor=await frontend_actor(request,row,headers)
        if actor.user_id!=row['account_id']:raise HTTPException(403,'delegation_identity_changed')
        return actor,row
    scope={**request.scope,'path':'/api/v1/connectors/ask','raw_path':b'/api/v1/connectors/ask',
        'headers':[(k.encode(),v.encode()) for k,v in headers.items()],'state':{},'root_path':'',
        'client':('127.0.0.1',0)}
    scope.pop('route',None)
    delegated=Request(scope);delegated.state.request_id=request.state.request_id
    actor=await request.app.state.auth.authenticate(delegated)
    if actor.user_id!=row['account_id']:raise HTTPException(403,'delegation_identity_changed')
    return actor,row

async def institutional_identity(request,actor):
    """Only the immutable, server-side AD binding can identify a SECP principal."""
    if getattr(actor,'key_id',None) is not None and not actor.can('data.query'):actor.require('data.query')
    if not actor.subject.startswith('webui:'):raise HTTPException(403,'Para acessar o SECP, use uma conta institucional vinculada; chaves compartilhadas de serviço não representam uma pessoa.')
    config=request.app.state.settings
    account=await request.app.state.db.execute('SELECT legacy_id,preferences FROM moara.accounts WHERE id=CAST(:id AS uuid)',{'id':str(actor.user_id)},one=True)
    identifier=str(uuid.UUID(str((account or {}).get('legacy_id') or actor.user_id)));stamp=str(int(time.time()))
    signature=hmac.new(config.forward_key.encode(),(stamp+':'+identifier).encode(),hashlib.sha256).hexdigest()
    try:
        result=await request.app.state.http.get(config.legacy_webui+'/api/v1/moara/internal/identity/'+identifier,
            headers={'X-Moara-Timestamp':stamp,'X-Moara-Signature':signature},timeout=5)
        value=result.json() if result.status_code==200 else {}
    except (httpx.HTTPError,ValueError):raise HTTPException(503,'Não foi possível verificar o vínculo institucional para consultar o SECP') from None
    if not value.get('enabled') or value.get('institutional_verified') is not True or not value.get('username') or not value.get('organization'):
        raise HTTPException(403,'Para consultar o SECP, entre novamente pelo login institucional, escolhendo sua unidade e usando sua matrícula e senha da rede. Contas locais da Moara não recebem acesso ao SECP automaticamente.')
    import re
    if not re.fullmatch(r'[A-Za-z0-9._-]{1,128}',value['username']) or not re.fullmatch(r'[A-Z][A-Z0-9-]{1,15}',value['organization']):raise HTTPException(403,'Vínculo institucional inválido')
    try:object_id=str(uuid.UUID(value['directory_object_id']))
    except (ValueError,KeyError,TypeError):raise HTTPException(403,'Vínculo institucional inválido') from None
    issuer=value.get('directory_fingerprint','')
    if not isinstance(issuer,str) or not re.fullmatch(r'[a-f0-9]{64}',issuer):raise HTTPException(403,'Entre novamente pelo login institucional para verificar a origem da identidade')
    profile=((account or {}).get('preferences') or {}).get('secp_profile')
    return {'username':value['username'],'organization':value['organization'],'object_id':object_id,'issuer':issuer,'profile':profile if isinstance(profile,str) else None}

@router.post('/secp-identity')
async def secp_identity(request:Request):
    actor,row=await verified(request)
    return {'authorized':True,'identity':await institutional_identity(request,actor)}

class Permission(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source_id:uuid.UUID
    purpose:str=Field(default='query',pattern='^(query|personnel|secp)$')

@router.post('/authorize-query')
async def authorize_query(body:Permission,request:Request):
    actor,row=await verified(request)
    if body.purpose=='secp':
        if not actor.can('data.query') and not row.get('_secp_operation'):actor.require('data.query')
        identity=await institutional_identity(request,actor)
    else:actor.require('data.query');identity=None
    if body.purpose=='personnel':actor.require('connectors.manage')
    if actor.allowed_sources is not None and str(body.source_id) not in actor.allowed_sources:raise HTTPException(404,'source_not_found')
    return {'authorized':True,**({'identity':identity} if identity else {})}

@router.post('/inference')
async def infer(body:Completion,request:Request):
    actor,row=await verified(request)
    if not actor.can('data.query'):
        if not row.get('_secp_operation'):actor.require('data.query')
        await institutional_identity(request,actor)
    actor.require('chat.use')
    if body.stream or body.model!=row['profile_id'] or not row['profile_id']:raise HTTPException(403,'delegated_profile_not_authorized')
    return await completion(body,request,actor)
