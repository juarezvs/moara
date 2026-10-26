"""Administrative accounts and separately revocable, narrowly scoped API keys."""
import asyncio
import secrets
import uuid
import httpx
from datetime import datetime,timezone,timedelta
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from .auth import require,PASSWORDS,PASSWORD_SLOTS,digest
from .rbac import ROLES,PERMISSIONS
from .database import as_json

router=APIRouter(prefix='/api/v1/admin',tags=['Access administration'])
class Strict(BaseModel):model_config=ConfigDict(extra='forbid')
class AccountCreate(Strict):
    name:str=Field(min_length=2,max_length=160)
    email:str=Field(min_length=5,max_length=200,pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    roles:list[str]=Field(min_length=1,max_length=7)
class AccountUpdate(Strict):
    active:bool
    roles:list[str]=Field(min_length=1,max_length=7)
class KeyCreate(Strict):
    account_id:uuid.UUID
    name:str=Field(min_length=2,max_length=120)
    scopes:list[str]=Field(min_length=1,max_length=30)
    allowed_profiles:list[str]=Field(min_length=1,max_length=30)
    allowed_sources:list[uuid.UUID]=Field(default_factory=list,max_length=100)
    rpm:int=Field(default=60,ge=1,le=600)
    validity_days:int=Field(default=90,ge=1,le=365)

ACCOUNT_COLUMNS='id,subject,name,email,auth_source,active,password_change_required,created_at,updated_at'

@router.get('/roles')
async def roles(request:Request,actor=Depends(require('users.read'))):
    return await request.app.state.db.execute('SELECT id,name,permissions FROM moara.roles ORDER BY id')

@router.get('/accounts')
async def accounts(request:Request,actor=Depends(require('users.read'))):
    return await request.app.state.db.execute('''SELECT a.id,a.subject,a.name,a.email,a.auth_source,a.active,a.password_change_required,a.created_at,
        COALESCE(jsonb_agg(r.role_id) FILTER(WHERE r.role_id IS NOT NULL),'[]') AS roles
        FROM moara.accounts a LEFT JOIN moara.account_roles r ON r.account_id=a.id GROUP BY a.id ORDER BY a.name LIMIT 1000''')

@router.post('/accounts/sync-institutional')
async def sync_institutional(request:Request,actor=Depends(require('users.manage'))):
    actor.require('roles.assign')
    if actor.key_id or not actor.legacy_token:raise HTTPException(409,'institutional_admin_session_required')
    auth=request.app.state.auth;users=[];started=datetime.now(timezone.utc)
    for page in range(1,101):
        try:response=await request.app.state.http.get(auth.settings.legacy_webui+'/api/v1/users/',params={'page':page},
            headers={'Authorization':'Bearer '+actor.legacy_token},timeout=15)
        except httpx.HTTPError:raise HTTPException(503,'institutional_directory_unavailable') from None
        if response.status_code!=200:raise HTTPException(403,'native_chat_administrator_required')
        value=response.json();rows=value.get('users',[]);users.extend(rows)
        if len(users)>=value['total']:break
        if not rows or len(users)>1000:raise HTTPException(409,'institutional_sync_limit_exceeded')
    else:raise HTTPException(409,'institutional_sync_limit_exceeded')
    if len(users)>1000:raise HTTPException(409,'institutional_sync_limit_exceeded')
    active={str(uuid.UUID(r['id'])) for r in users if r.get('role') in ('user','admin')}
    if str(actor.user_id) not in active:raise HTTPException(409,'incomplete_institutional_inventory')
    imported=0;kept_disabled=0
    for row in users:
        if row.get('role') not in ('user','admin'):continue
        try:await auth.upsert_legacy(row);imported+=1
        except HTTPException as error:
            if error.status_code==403 and error.detail=='account_disabled':kept_disabled+=1
            else:raise
    # A full, authenticated native inventory is required before suspending any
    # missing/pending native account. Independent integration/local accounts stay.
    suspended=0
    for row in await auth.db.execute("SELECT id FROM moara.accounts WHERE auth_source='legacy' AND active AND created_at<=:started",{'started':started}):
        if str(row['id']) not in active:
            await auth.db.execute('UPDATE moara.accounts SET active=false,session_version=session_version+1,updated_at=now() WHERE id=CAST(:id AS uuid)',{'id':str(row['id'])})
            suspended+=1
    await auth.db.audit(actor,'account.institutional_sync',status='ok',request_id=request.state.request_id)
    return {'synchronized':imported,'kept_disabled':kept_disabled,'suspended':suspended,'roles_overwritten':False}

def validate_roles(roles):
    if not set(roles)<=ROLES.keys():raise HTTPException(422,'invalid_roles')

@router.post('/accounts',status_code=201)
async def create_account(body:AccountCreate,request:Request,actor=Depends(require('users.manage'))):
    actor.require('roles.assign');validate_roles(body.roles)
    db=request.app.state.db;identifier=uuid.uuid4();password=secrets.token_urlsafe(24)
    async with PASSWORD_SLOTS:hashed=await asyncio.to_thread(PASSWORDS.hash,password)
    async with db.engine.begin() as conn:
        await db.execute('SELECT pg_advisory_xact_lock(42612554)',conn=conn)
        existing=await db.execute('SELECT id FROM moara.accounts WHERE lower(email)=:email',{'email':body.email.casefold()},one=True,conn=conn)
        if existing:raise HTTPException(409,'account_email_exists')
        await db.execute('''INSERT INTO moara.accounts(id,subject,name,email,auth_source,password_hash,password_change_required)
            VALUES(CAST(:id AS uuid),:subject,:name,:email,'local',:hash,true)''',
            {'id':str(identifier),'subject':'local:'+str(identifier),'name':body.name,'email':body.email.casefold(),'hash':hashed},conn=conn)
        for role in set(body.roles):
            await db.execute('INSERT INTO moara.account_roles(account_id,role_id) VALUES(CAST(:id AS uuid),:role)',{'id':str(identifier),'role':role},conn=conn)
        await db.audit(actor,'account.create',identifier,request_id=request.state.request_id,conn=conn)
    return {'id':str(identifier),'temporary_password':password,'display_once':True,'password_change_required':True}

@router.put('/accounts/{identifier}')
async def update_account(identifier:uuid.UUID,body:AccountUpdate,request:Request,actor=Depends(require('users.manage'))):
    actor.require('roles.assign');validate_roles(body.roles);db=request.app.state.db
    async with db.engine.begin() as conn:
        await db.execute('SELECT pg_advisory_xact_lock(42612554)',conn=conn)
        target=await db.execute('SELECT id FROM moara.accounts WHERE id=CAST(:id AS uuid)',{'id':str(identifier)},one=True,conn=conn)
        if not target:raise HTTPException(404,'account_not_found')
        if not body.active or 'administrator' not in body.roles:
            others=await db.execute('''SELECT a.id FROM moara.accounts a JOIN moara.account_roles r ON r.account_id=a.id
                WHERE a.active AND r.role_id='administrator' AND a.id<>CAST(:id AS uuid) LIMIT 1''',{'id':str(identifier)},one=True,conn=conn)
            was_admin=await db.execute("SELECT role_id FROM moara.account_roles WHERE account_id=CAST(:id AS uuid) AND role_id='administrator'",{'id':str(identifier)},one=True,conn=conn)
            if was_admin and not others:raise HTTPException(409,'last_administrator_required')
        await db.execute('UPDATE moara.accounts SET active=:active,session_version=session_version+1,updated_at=now() WHERE id=CAST(:id AS uuid)',
            {'id':str(identifier),'active':body.active},conn=conn)
        await db.execute('DELETE FROM moara.account_roles WHERE account_id=CAST(:id AS uuid)',{'id':str(identifier)},conn=conn)
        for role in set(body.roles):
            await db.execute('INSERT INTO moara.account_roles(account_id,role_id) VALUES(CAST(:id AS uuid),:role)',{'id':str(identifier),'role':role},conn=conn)
        await db.audit(actor,'account.permissions.update',identifier,request_id=request.state.request_id,conn=conn)
    return {'updated':True,'sessions_revoked':True}

@router.get('/api-keys')
async def list_keys(request:Request,actor=Depends(require('api_keys.manage'))):
    return await request.app.state.db.execute('''SELECT k.id,k.account_id,a.name AS account_name,k.name,k.scopes,k.allowed_profiles,k.allowed_sources,k.rpm,
        k.created_at,k.expires_at,k.revoked_at,k.last_used_at FROM moara.api_keys k JOIN moara.accounts a ON a.id=k.account_id ORDER BY k.created_at DESC LIMIT 500''')

@router.post('/api-keys',status_code=201)
async def create_key(body:KeyCreate,request:Request,actor=Depends(require('api_keys.manage'))):
    # Management and identity-publication credentials must remain interactive.
    allowed={'chat.use','profiles.read','identity.read','connectors.read','data.query','jobs.read','jobs.cancel'}
    if not set(body.scopes)<=allowed:raise HTTPException(422,'integration_scope_not_allowed')
    db=request.app.state.db
    account=await db.execute('SELECT * FROM moara.accounts WHERE id=CAST(:id AS uuid)',{'id':str(body.account_id)},one=True)
    if not account or not account['active']:raise HTTPException(404,'account_not_found')
    owner=await request.app.state.auth.from_row(account)
    if any(not owner.can(scope) for scope in body.scopes):raise HTTPException(403,'key_exceeds_owner_permissions')
    from .catalog_api import visible_profiles
    permitted={p['id'] for p in await visible_profiles(db,owner)}
    if not set(body.allowed_profiles)<=permitted:raise HTTPException(403,'profile_not_authorized')
    identifier=uuid.uuid4();token='moara_'+secrets.token_urlsafe(40);expires=datetime.now(timezone.utc)+timedelta(days=body.validity_days)
    async with db.engine.begin() as conn:
        await db.execute('''INSERT INTO moara.api_keys(id,account_id,name,token_hash,scopes,allowed_profiles,allowed_sources,rpm,expires_at,created_by)
            VALUES(CAST(:id AS uuid),CAST(:owner AS uuid),:name,:hash,CAST(:scopes AS jsonb),CAST(:profiles AS jsonb),CAST(:sources AS jsonb),:rpm,:expires,CAST(:creator AS uuid))''',
            {'id':str(identifier),'owner':str(body.account_id),'name':body.name,'hash':digest(token),'scopes':as_json(sorted(set(body.scopes))),
                'profiles':as_json(sorted(set(body.allowed_profiles))),'sources':as_json(sorted({str(s) for s in body.allowed_sources})),
                'rpm':body.rpm,'expires':expires,'creator':str(actor.user_id)},conn=conn)
        await db.audit(actor,'api_key.create',identifier,request_id=request.state.request_id,conn=conn)
    return {'id':str(identifier),'token':token,'display_once':True,'expires_at':expires}

@router.post('/api-keys/{identifier}/revoke')
async def revoke_key(identifier:uuid.UUID,request:Request,actor=Depends(require('api_keys.manage'))):
    db=request.app.state.db
    async with db.engine.begin() as conn:
        row=await db.execute('UPDATE moara.api_keys SET revoked_at=COALESCE(revoked_at,now()) WHERE id=CAST(:id AS uuid) RETURNING id',{'id':str(identifier)},one=True,conn=conn)
        if not row:raise HTTPException(404,'api_key_not_found')
        await db.audit(actor,'api_key.revoke',identifier,request_id=request.state.request_id,conn=conn)
    return {'revoked':True}
