import asyncio
import hmac
import hashlib
import uuid
from datetime import datetime,timezone
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field
from .auth import current_actor,PASSWORDS,PASSWORD_SLOTS
from argon2.exceptions import VerificationError,InvalidHashError
from .database import as_json

router=APIRouter(prefix='/api/v1/auth',tags=['Authentication'])
class Strict(BaseModel):model_config=ConfigDict(extra='forbid')
class Login(Strict):
    email:str=Field(min_length=3,max_length=200)
    password:str=Field(min_length=1,max_length=256)
class Password(Strict):
    password:str=Field(min_length=16,max_length=256)
    current_password:str|None=Field(default=None,max_length=256)
class Preferences(Strict):
    theme:Literal['light','dark']|None=None
    welcome_seen:bool|None=None

def session_response(auth,token,expires):
    csrf=hmac.new(auth.settings.session_key,token.encode(),hashlib.sha256).hexdigest()
    response=JSONResponse({'authenticated':True,'csrf_token':csrf,'expires_at':expires.isoformat()})
    response.set_cookie(auth.settings.session_cookie,token,secure=True,httponly=True,samesite='strict',path='/moara',
        max_age=max(0,int((expires-datetime.now(timezone.utc)).total_seconds())))
    return response

@router.post('/login')
async def login(body:Login,request:Request):
    auth=request.app.state.auth;auth.origin(request)
    row,legacy=await auth.password_login(body.email.strip(),body.password,request.client.host if request.client else 'unknown')
    token,expires=await auth.session(row,legacy)
    actor=await auth.from_row(row)
    await auth.db.audit(actor,'auth.login',request_id=request.state.request_id)
    return session_response(auth,token,expires)

@router.post('/session')
async def bridge(request:Request):
    auth=request.app.state.auth;auth.origin(request)
    header=request.headers.get('authorization','')
    if not header.startswith('Bearer ') or header[7:].count('.')!=2 or len(header)>4100:raise HTTPException(401,'verified_institutional_session_required')
    row=await auth.legacy_user(header[7:]);token,expires=await auth.session(row,header[7:])
    await auth.db.audit(await auth.from_row(row),'auth.bridge',request_id=request.state.request_id)
    return session_response(auth,token,expires)

@router.get('/me')
async def me(actor=Depends(current_actor)):return actor.public()

@router.post('/logout')
async def logout(request:Request,actor=Depends(current_actor)):
    if actor.session_id:
        await request.app.state.db.execute('UPDATE moara.sessions SET revoked_at=now() WHERE id=CAST(:id AS uuid)',{'id':str(actor.session_id)})
    await request.app.state.db.audit(actor,'auth.logout',request_id=request.state.request_id)
    legacy_logout=True
    if actor.legacy_token:
        try:
            result=await request.app.state.http.post(request.app.state.settings.legacy_webui+'/api/v1/auths/signout',
                headers={'Authorization':'Bearer '+actor.legacy_token},timeout=10)
            legacy_logout=result.status_code in (200,401)
        except Exception:legacy_logout=False
    response=JSONResponse({'authenticated':False,'legacy_logout_confirmed':legacy_logout})
    response.delete_cookie(request.app.state.settings.session_cookie,path='/moara',secure=True,httponly=True,samesite='strict')
    response.delete_cookie('studio_token',path='/studio',secure=True,httponly=True,samesite='strict')
    for name in ['token','owui-session','oui-session','oauth_id_token','oauth_session_id']:
        response.delete_cookie(name,path='/',secure=True,httponly=True)
    return response

@router.put('/preferences')
async def preferences(body:Preferences,request:Request,actor=Depends(current_actor)):
    if actor.key_id or actor.auth_source=='integration':raise HTTPException(403,'interactive_session_required')
    await request.app.state.db.execute("UPDATE moara.accounts SET preferences=preferences || CAST(:preferences AS jsonb) WHERE id=CAST(:id AS uuid)",
        {'id':str(actor.user_id),'preferences':as_json(body.model_dump(exclude_none=True))})
    return body.model_dump(exclude_none=True)

@router.put('/password')
async def password(body:Password,request:Request,actor=Depends(current_actor)):
    if actor.auth_source!='local' or actor.key_id:raise HTTPException(409,'use_institutional_password_management')
    if not actor.password_change_required:
        row=await request.app.state.db.execute('SELECT password_hash FROM moara.accounts WHERE id=CAST(:id AS uuid)',{'id':str(actor.user_id)},one=True)
        async with PASSWORD_SLOTS:
            def verify():
                try:return PASSWORDS.verify(row['password_hash'],body.current_password or '')
                except (VerificationError,InvalidHashError):return False
            if not await asyncio.to_thread(verify):raise HTTPException(401,'invalid_credentials')
    async with PASSWORD_SLOTS:hashed=await asyncio.to_thread(PASSWORDS.hash,body.password)
    db=request.app.state.db
    async with db.engine.begin() as conn:
        row=await db.execute('''UPDATE moara.accounts SET password_hash=:hash,password_change_required=false,session_version=session_version+1,updated_at=now()
            WHERE id=CAST(:id AS uuid) RETURNING session_version''',{'id':str(actor.user_id),'hash':hashed},one=True,conn=conn)
        if actor.session_id:
            await db.execute('UPDATE moara.sessions SET session_version=:version WHERE id=CAST(:id AS uuid)',{'id':str(actor.session_id),'version':row['session_version']},conn=conn)
        await db.audit(actor,'auth.password.update',request_id=request.state.request_id,conn=conn)
    return {'changed':True,'other_sessions_revoked':True}
