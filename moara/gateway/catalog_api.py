"""Physical inventory and permission-filtered execution profiles.

Only bindings verified by provisioning are executable. User input cannot select a
provider URL, arbitrary Ollama tag, or bypass a profile's object ACL.
"""
import uuid
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from .auth import require
from .database import as_json

router=APIRouter(prefix='/api/v1',tags=['Model catalog'])
compat_router=APIRouter(tags=['OpenAI compatibility'])

async def visible_profiles(db,actor):
    rows=await db.execute('SELECT * FROM moara.profiles WHERE enabled=true ORDER BY name,id')
    memberships=await db.execute('SELECT group_id FROM moara.group_members WHERE account_id=CAST(:id AS uuid)',{'id':str(actor.user_id)})
    groups={str(r['group_id']) for r in memberships}
    result=[]
    for row in rows:
        if actor.allowed_profiles is not None and row['id'] not in actor.allowed_profiles:continue
        # The initial chat role includes the shared principal, never arbitrary model profiles.
        default_chat=(row['id']=='gemma4-12b' and 'user' in actor.roles and actor.can('chat.use') and actor.auth_source!='integration')
        permitted=default_chat or actor.can('profiles.manage') or bool(actor.key_id and getattr(actor,'owner_profiles_manage',False)) or row['public'] or actor.subject in row['allowed_subjects'] or groups.intersection(row['allowed_groups'])
        # Existing integration keys retain their previously authorized aliases.
        if actor.auth_source=='integration' and actor.upstream_key and row['legacy_compatible']:permitted=True
        if permitted:result.append(row)
    return result

async def candidates(db,profile):
    return await db.execute('''SELECT m.*,b.id AS binding_id,b.legacy_alias,b.context_length,b.threads,b.ready,pm.priority
        FROM moara.profile_models pm JOIN moara.models m ON m.id=pm.model_id
        JOIN moara.execution_bindings b ON b.model_id=m.id
        WHERE pm.profile_id=:id AND m.enabled AND m.installed AND b.ready
        AND b.context_length=:context AND b.threads=:threads ORDER BY pm.priority,m.id''',
        {'id':profile['id'],'context':profile['settings'].get('context_length',8192),'threads':profile['settings'].get('threads',12)})

@router.get('/profiles')
@router.get('/models/profiles')
async def profiles(request:Request,actor=Depends(require('profiles.read'))):
    result=[]
    for p in await visible_profiles(request.app.state.db,actor):
        models=await candidates(request.app.state.db,p)
        result.append({k:p[k] for k in ('id','name','description','category','manual_allowed','settings')}|{
            'available':bool(models),'models':[{'id':str(m['id']),'name':m['display_name'],'capabilities':m['capabilities']} for m in models]})
    return result

@compat_router.get('/v1/models')
async def openai_models(request:Request,actor=Depends(require('profiles.read'))):
    available=[]
    for profile in await visible_profiles(request.app.state.db,actor):
        if await candidates(request.app.state.db,profile):available.append(profile)
    data=[{'id':p['id'],'object':'model','created':0,'owned_by':'moara','name':p['name']} for p in available]
    if actor.can('development.use') and any(p['id']=='general' and p['manual_allowed'] for p in available):
        data.insert(0,{'id':'moara-code','object':'model','created':0,'owned_by':'moara','name':'Moara Desenvolvedora'})
    if any(p['settings'].get('auto_eligible',p['id'] in {'coding','general','fast'}) for p in available):
        data.insert(0,{'id':'auto','object':'model','created':0,'owned_by':'moara','name':'Moara AI · Automático'})
    return {'object':'list','data':data}

@compat_router.get('/v1/models/{identifier}')
async def openai_model(identifier:str,request:Request,actor=Depends(require('profiles.read'))):
    values=await openai_models(request,actor)
    model=next((m for m in values['data'] if m['id']==identifier),None)
    if model is None:raise HTTPException(404,'model_not_found')
    return model

@router.get('/models')
async def models(request:Request,actor=Depends(require('models.read'))):
    return await request.app.state.db.execute('SELECT * FROM moara.models ORDER BY display_name,id')

class ProfileSettings(BaseModel):
    model_config=ConfigDict(extra='forbid')
    context_length:int=Field(ge=2048,le=16384)
    threads:int=Field(ge=1,le=16)
    temperature:float=Field(ge=0,le=2)
    max_tokens:int=Field(ge=32,le=4096)
    timeout:int=Field(ge=30,le=1200)
    reasoning_effort:str|None=Field(default=None,pattern='^(none|low|medium|high)$')
    auto_eligible:bool|None=None

class ModelActivation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    active:bool

@router.put('/admin/models/{identifier}/activation')
async def model_activation(identifier:uuid.UUID,body:ModelActivation,request:Request,actor=Depends(require('models.manage'))):
    if actor.key_id or actor.auth_source=='integration':raise HTTPException(403,'interactive_session_required')
    db=request.app.state.db
    async with db.engine.begin() as conn:
        model=await db.execute('SELECT * FROM moara.models WHERE id=CAST(:id AS uuid) FOR UPDATE',{'id':str(identifier)},one=True,conn=conn)
        if not model:raise HTTPException(404,'model_not_found')
        if body.active:
            binding=await db.execute('SELECT id FROM moara.execution_bindings WHERE model_id=CAST(:id AS uuid) AND ready LIMIT 1',{'id':str(identifier)},one=True,conn=conn)
            if not model['installed'] or not binding:raise HTTPException(409,'execution_configuration_not_provisioned')
            if not model['protected']:
                from .model_catalog import APPROVED
                approved=APPROVED.get(model['settings'].get('catalog_id'))
                if not approved:raise HTTPException(409,'model_not_in_approved_catalog')
                needed={'embedding'} if approved['embedding'] else {'text','code'} if approved['category']=='coding' else {'text'}
                samples=await db.execute('''SELECT DISTINCT parameters->>'case' AS fixture FROM moara.benchmark_samples
                    WHERE model_id=CAST(:id AS uuid) AND parameters->>'context_length'='8192' AND parameters->>'threads'='12'
                    AND quality->>'passed'='true' ''',{'id':str(identifier)},conn=conn)
                if not needed<={r['fixture'] for r in samples}:raise HTTPException(409,'model_validation_required')
        await db.execute('UPDATE moara.models SET enabled=:active,updated_at=now() WHERE id=CAST(:id AS uuid)',{'id':str(identifier),'active':body.active},conn=conn)
        await db.audit(actor,'model.activate' if body.active else 'model.deactivate',identifier,request_id=request.state.request_id,conn=conn)
    return {'id':str(identifier),'enabled':body.active,'scope':'new_moara_platform','legacy_chat_configuration_changed':False}

class ProfileUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=2,max_length=120)
    description:str=Field(max_length=1200)
    enabled:bool
    manual_allowed:bool
    public:bool
    allowed_subjects:list[str]=Field(max_length=100)
    allowed_groups:list[uuid.UUID]=Field(max_length=100)
    settings:ProfileSettings

class ProfileCreate(ProfileUpdate):
    id:str=Field(min_length=2,max_length=64,pattern=r'^[a-z][a-z0-9_-]+$')
    category:str=Field(pattern='^(fast|general|coding)$')
    model_ids:list[uuid.UUID]=Field(min_length=1,max_length=8)

@router.post('/admin/profiles',status_code=201)
async def create_profile(body:ProfileCreate,request:Request,actor=Depends(require('profiles.manage'))):
    if body.id=='auto':raise HTTPException(409,'reserved_profile_id')
    if len(set(body.model_ids))!=len(body.model_ids):raise HTTPException(422,'duplicate_model_binding')
    if any(len(s)>130 or not s.startswith(('webui:','local:','key:')) for s in body.allowed_subjects):raise HTTPException(422,'invalid_profile_subject')
    settings=body.settings.model_dump(exclude_none=True)
    if settings['max_tokens']>=settings['context_length']:raise HTTPException(422,'completion_exceeds_context')
    db=request.app.state.db
    async with db.engine.begin() as conn:
        await db.execute('SELECT pg_advisory_xact_lock(42612556)',conn=conn)
        if await db.execute('SELECT id FROM moara.profiles WHERE id=:id',{'id':body.id},one=True,conn=conn):raise HTTPException(409,'profile_already_exists')
        for model in body.model_ids:
            row=await db.execute('''SELECT m.capabilities FROM moara.models m JOIN moara.execution_bindings b ON b.model_id=m.id
                WHERE m.id=CAST(:id AS uuid) AND m.installed AND m.enabled AND b.ready AND b.context_length=:context AND b.threads=:threads
                LIMIT 1 FOR SHARE OF m''',{'id':str(model),'context':settings['context_length'],'threads':settings['threads']},one=True,conn=conn)
            if not row or not row['capabilities'].get('completion'):raise HTTPException(409,'execution_configuration_not_provisioned')
        await db.execute('''INSERT INTO moara.profiles(id,name,description,category,enabled,manual_allowed,public,allowed_subjects,allowed_groups,settings)
            VALUES(:id,:name,:description,:category,:enabled,:manual,:public,CAST(:subjects AS jsonb),CAST(:groups AS jsonb),CAST(:settings AS jsonb))''',
            {'id':body.id,'name':body.name,'description':body.description,'category':body.category,'enabled':body.enabled,'manual':body.manual_allowed,
             'public':body.public,'subjects':as_json(sorted(set(body.allowed_subjects))),'groups':as_json(sorted({str(g) for g in body.allowed_groups})),
             'settings':as_json(settings)},conn=conn)
        for priority,model in enumerate(body.model_ids):
            await db.execute('INSERT INTO moara.profile_models(profile_id,model_id,priority) VALUES(:profile,CAST(:model AS uuid),:priority)',
                {'profile':body.id,'model':str(model),'priority':priority},conn=conn)
        await db.audit(actor,'profile.create',body.id,request_id=request.state.request_id,conn=conn)
    return {'id':body.id,'created':True}

@router.get('/admin/profiles')
async def admin_profiles(request:Request,actor=Depends(require('profiles.manage'))):
    return await request.app.state.db.execute('SELECT * FROM moara.profiles ORDER BY name,id')

@router.put('/admin/profiles/{identifier}')
async def update_profile(identifier:str,body:ProfileUpdate,request:Request,actor=Depends(require('profiles.manage'))):
    db=request.app.state.db
    async with db.engine.begin() as conn:
        old=await db.execute('SELECT * FROM moara.profiles WHERE id=:id FOR UPDATE',{'id':identifier},one=True,conn=conn)
        if not old:raise HTTPException(404,'profile_not_found')
        if any(len(s)>130 or not s.startswith(('webui:','local:','key:')) for s in body.allowed_subjects):raise HTTPException(422,'invalid_profile_subject')
        settings=body.settings.model_dump(exclude_none=True)
        binding=await db.execute('''SELECT b.id FROM moara.execution_bindings b JOIN moara.profile_models p ON p.model_id=b.model_id JOIN moara.models m ON m.id=b.model_id
            WHERE p.profile_id=:id AND b.ready AND m.enabled AND m.installed AND b.context_length=:context AND b.threads=:threads LIMIT 1 FOR SHARE OF m''',
            {'id':identifier,'context':settings['context_length'],'threads':settings['threads']},one=True,conn=conn)
        if body.enabled and not binding:raise HTTPException(409,'execution_configuration_not_provisioned')
        if settings['max_tokens']>=settings['context_length']:raise HTTPException(422,'completion_exceeds_context')
        # Preserve execution adapter metadata; it cannot be supplied by clients.
        settings={**old['settings'],**settings}
        await db.execute('''UPDATE moara.profiles SET name=:name,description=:description,enabled=:enabled,manual_allowed=:manual,
            public=:public,allowed_subjects=CAST(:subjects AS jsonb),allowed_groups=CAST(:groups AS jsonb),settings=CAST(:settings AS jsonb),updated_at=now() WHERE id=:id''',
            {'id':identifier,'name':body.name,'description':body.description,'enabled':body.enabled,'manual':body.manual_allowed,'public':body.public,
                'subjects':as_json(sorted(set(body.allowed_subjects))),'groups':as_json(sorted({str(g) for g in body.allowed_groups})),'settings':as_json(settings)},conn=conn)
        await db.audit(actor,'profile.update',identifier,request_id=request.state.request_id,conn=conn)
    return {'updated':True,'id':identifier}
