"""Versioned official assistants; central permissions cannot be edited as prompts."""
import json
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from .auth import require
from .platform_store import digest

router=APIRouter(prefix='/api/v1/assistants',tags=['Official assistants'])
BASE={item['id']:item for item in json.loads((Path(__file__).resolve().parents[1]/'assistants/catalog.json').read_text(encoding='utf-8'))}
POLICY_VERSION='2.0.0'


class Update(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision:int=Field(ge=1)
    enabled:bool
    instructions:str=Field(min_length=20,max_length=6000)
    tools:list[str]=Field(max_length=12)


def validate_definition(identifier,value):
    if identifier not in BASE or set(value)!={'enabled','instructions','tools'}:raise HTTPException(422,'invalid_assistant_definition')
    if not isinstance(value['enabled'],bool) or not isinstance(value['instructions'],str) or not 20<=len(value['instructions'])<=6000:
        raise HTTPException(422,'invalid_assistant_definition')
    tools=value['tools']
    if not isinstance(tools,list) or any(not isinstance(t,str) or t not in BASE[identifier]['tools'] for t in tools):
        raise HTTPException(422,'assistant_tool_not_permitted')
    return {**value,'tools':sorted(set(tools))}


async def initialize(app):
    db=app.state.db
    async with db.engine.begin() as conn:
        await db.execute('SELECT pg_advisory_xact_lock(42612561)',conn=conn)
        for identifier,base in BASE.items():
            definition=validate_definition(identifier,{'enabled':True,'instructions':base['instructions'],'tools':base['tools']})
            rows=await db.execute('''INSERT INTO moara.official_assistants(id,definition,sha256,updated_by)
                VALUES(:id,CAST(:definition AS jsonb),:sha,'deployment:moara2') ON CONFLICT(id) DO NOTHING RETURNING id''',
                {'id':identifier,'definition':json.dumps(definition,ensure_ascii=False),'sha':digest(definition)},conn=conn)
            if rows:
                await db.execute('''INSERT INTO moara.official_assistant_versions(assistant_id,revision,definition,sha256,author)
                    VALUES(:id,1,CAST(:definition AS jsonb),:sha,'deployment:moara2')''',
                    {'id':identifier,'definition':json.dumps(definition,ensure_ascii=False),'sha':digest(definition)},conn=conn)


def materialize(row,actor,admin=False):
    base=BASE[row['id']];definition=validate_definition(row['id'],row['definition'])
    if digest(definition)!=row['sha256']:raise HTTPException(503,'assistant_integrity_failed')
    allowed=definition['enabled'] and all(actor.can(p) for p in base['permissions'])
    value={k:base[k] for k in ('id','name','version','description','mission')}
    value.update(revision=row['revision'],enabled=definition['enabled'],authorized=allowed,
        required_permissions=base['permissions'],tools=definition['tools'],policy_version=POLICY_VERSION,
        prompt_sha256=row['sha256'],model_policy='shared_principal_authorized',requires_human_review=True)
    if admin:value.update(instructions=definition['instructions'],tool_catalog=base['tools'],updated_by=row['updated_by'],updated_at=row['updated_at'])
    return value


async def resolve(app,actor,identifier):
    if identifier not in BASE:raise HTTPException(422,'invalid_assistant')
    row=await app.state.db.execute('SELECT * FROM moara.official_assistants WHERE id=:id',{'id':identifier},one=True)
    if not row:raise HTTPException(503,'assistant_catalog_unavailable')
    value=materialize(row,actor,True)
    if not value['enabled']:raise HTTPException(409,'assistant_disabled')
    if not value['authorized']:raise HTTPException(403,'assistant_not_authorized')
    return value


@router.get('')
async def catalog(request:Request,actor=Depends(require('chat.use'))):
    rows=await request.app.state.db.execute('SELECT * FROM moara.official_assistants ORDER BY id')
    return [materialize(row,actor) for row in rows if row['id'] in BASE]


@router.get('/admin/catalog')
async def admin_catalog(request:Request,actor=Depends(require('profiles.manage'))):
    rows=await request.app.state.db.execute('SELECT * FROM moara.official_assistants ORDER BY id')
    return [materialize(row,actor,True) for row in rows if row['id'] in BASE]


@router.get('/admin/{identifier}/versions')
async def versions(identifier:str,request:Request,actor=Depends(require('profiles.manage'))):
    if identifier not in BASE:raise HTTPException(404,'assistant_not_found')
    rows=await request.app.state.db.execute('SELECT * FROM moara.official_assistant_versions WHERE assistant_id=:id ORDER BY revision DESC LIMIT 100',{'id':identifier})
    if any(digest(validate_definition(identifier,row['definition']))!=row['sha256'] for row in rows):raise HTTPException(503,'assistant_integrity_failed')
    return rows


@router.put('/admin/{identifier}')
async def update(identifier:str,body:Update,request:Request,actor=Depends(require('profiles.manage'))):
    definition=validate_definition(identifier,body.model_dump(exclude={'expected_revision'}))
    db=request.app.state.db;checksum=digest(definition)
    async with db.engine.begin() as conn:
        row=await db.execute('SELECT * FROM moara.official_assistants WHERE id=:id FOR UPDATE',{'id':identifier},one=True,conn=conn)
        if not row:raise HTTPException(404,'assistant_not_found')
        if row['revision']!=body.expected_revision:raise HTTPException(409,'assistant_revision_conflict')
        values={'id':identifier,'definition':json.dumps(definition,ensure_ascii=False),'sha':checksum,'actor':actor.subject,'revision':row['revision']+1}
        await db.execute('''UPDATE moara.official_assistants SET definition=CAST(:definition AS jsonb),sha256=:sha,
            revision=:revision,updated_by=:actor,updated_at=now() WHERE id=:id''',values,conn=conn)
        await db.execute('''INSERT INTO moara.official_assistant_versions(assistant_id,revision,definition,sha256,author)
            VALUES(:id,:revision,CAST(:definition AS jsonb),:sha,:actor)''',values,conn=conn)
        await db.audit(actor,'assistant.version.published',identifier,request_id=request.state.request_id,conn=conn)
    return {'id':identifier,'revision':values['revision'],'sha256':checksum,'policy_version':POLICY_VERSION}
