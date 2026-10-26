"""Explicit RBAC bridge to the isolated, read-only connector services.

Identity is built from the verified Moara actor. Caller-supplied role, owner,
service authorization and source restriction headers are never forwarded.
"""
import json
import re
import uuid
import httpx
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import Response
from .auth import current_actor
from .catalog_api import visible_profiles
from . import connector_tickets
router=APIRouter(prefix='/api/v1/connectors',tags=['Data sources'])
ID=r'[0-9a-fA-F-]{36}'
KIND=r'(?:postgres|mysql|mssql|oracle|mongodb|sqlite|rest)'
RULES=[
    ('GET',r'types','connectors.read'),('GET',r'dashboard','connectors.manage'),
    ('GET',r'sources','connectors.read'),('POST',r'sources','connectors.manage'),
    ('GET',rf'sources/{ID}','connectors.read'),('PUT',rf'sources/{ID}','connectors.manage'),
    ('DELETE',rf'sources/{ID}','connectors.manage'),
    ('PUT',rf'sources/{ID}/personnel-analytics','connectors.manage'),
    ('POST',rf'sources/{ID}/(?:test|discover|activation|semantic-index)','connectors.manage'),
    ('POST',rf'sources/{ID}/(?:query|preview)','data.query'),('GET',rf'sources/{ID}/history','connectors.read'),
    ('GET',r'groups','groups.manage'),('POST',r'groups','groups.manage'),('PUT',rf'groups/{ID}','groups.manage'),
    ('DELETE',rf'groups/{ID}','groups.manage'),
    ('GET',r'relationships','connectors.read'),('POST',r'relationships','connectors.manage'),
    ('DELETE',rf'relationships/{ID}','connectors.manage'),
    ('GET',rf'types/{KIND}/(?:settings|logs)','connectors.manage'),('PUT',rf'types/{KIND}/settings','connectors.manage'),
    ('POST',r'sqlite/import','connectors.manage'),('GET',r'audit','audit.read'),
    ('GET',r'models','profiles.read'),('POST',r'ask','data.query'),('POST',r'cross-query','data.query'),
    ('GET',r'runs','data.query'),('GET',rf'runs/{ID}','data.query'),('POST',rf'runs/{ID}/cancel','data.query'),
    ('POST',r'mcp','data.query'),
]

@router.api_route('',methods=['GET','POST'])
async def connector_registry(request:Request,actor=Depends(current_actor)):
    return await proxy('types' if request.method=='GET' else 'sources',request,actor)

@router.api_route('/{path:path}',methods=['GET','POST','PUT','DELETE'])
async def proxy(path:str,request:Request,actor=Depends(current_actor)):
    # Stable compact source URLs coexist with the explicit administrative paths.
    if re.fullmatch(ID,path):path='sources/'+path
    else:
        match=re.fullmatch(rf'({ID})/(test|queries|schemas)',path)
        if match:
            source_id,operation=match.groups()
            if operation=='schemas' and request.method=='GET':
                response=await proxy('sources/'+source_id,request,actor)
                if response.status_code!=200:return response
                value=json.loads(response.body);objects=value.get('objects') or value.get('policy',{}).get('objects',{})
                return {'source_id':source_id,'schemas':sorted({name.split('.')[0] for name in objects if '.' in name}),'objects':objects}
            path='sources/'+source_id+'/'+('query' if operation=='queries' else operation)
    required=next((permission for method,pattern,permission in RULES if method==request.method and re.fullmatch(pattern,path)),None)
    if required is None:raise HTTPException(404,'endpoint_not_found')
    actor.require(required)
    raw=await request.body()
    permitted_profiles=None
    if path in ('ask','models'):
        permitted_profiles={p['id'] for p in await visible_profiles(request.app.state.db,actor)}
    if path=='ask':
        actor.require('chat.use')
        try:body=json.loads(raw)
        except ValueError:raise HTTPException(422,'invalid_request') from None
        if not isinstance(body,dict) or body.get('model','coding') not in permitted_profiles:raise HTTPException(403,'profile_not_authorized')
    # Only the audit endpoint elevates an auditor's transport role; it cannot query data.
    administrative=actor.can('connectors.manage') or (path.startswith('groups') and actor.can('groups.manage')) or (path=='audit' and actor.can('audit.read'))
    headers={'Authorization':'Bearer '+request.app.state.settings.connector_key,'X-Actor-Id':actor.subject,
        'X-Actor-Admin':str(administrative).lower(),'Content-Type':'application/octet-stream' if path=='sqlite/import' else 'application/json'}
    if actor.allowed_sources is not None:headers['X-Actor-Source-Ids']=json.dumps(list(actor.allowed_sources),separators=(',',':'))
    if request.method=='POST' and (path in ('ask','cross-query','mcp') or path.endswith(('/query','/preview'))):
        profile=body.get('model','coding') if path=='ask' else None
        headers['X-Moara-Execution-Ticket']=await connector_tickets.issue(request,actor,profile)
    if request.headers.get('origin'):headers['Origin']=request.headers['origin']
    from opentelemetry.propagate import inject
    inject(headers)
    endpoint='/mcp' if path=='mcp' else '/v1/'+path
    try:
        result=await request.app.state.http.request(request.method,request.app.state.settings.connector_hub+endpoint,
            content=raw,headers=headers,timeout=httpx.Timeout(210 if path.endswith('/semantic-index') else 45,connect=5))
    except httpx.HTTPError:raise HTTPException(503,'connector_center_unavailable') from None
    # The administrative registry includes discovered catalogs for all sources.
    # Business-query responses retain their smaller bound.
    budget=(16 if path=='sources' and request.method=='GET' and actor.can('connectors.manage') else 4)*1024**2
    if len(result.content)>budget:raise HTTPException(502,'connector_response_too_large')
    if path=='models' and result.status_code==200:
        return [m for m in result.json() if m.get('id') in permitted_profiles]
    await request.app.state.db.audit(actor,'connector.'+('read' if request.method=='GET' else 'operation'),path,
        status='ok' if result.status_code<400 else 'error',error=str(result.status_code) if result.status_code>=400 else None,request_id=request.state.request_id)
    return Response(result.content,status_code=result.status_code,media_type='application/json')
