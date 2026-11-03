"""Read prior conversations under their owner's verified institutional session."""
import json,uuid
from datetime import datetime,timezone,timedelta
import httpx
from fastapi import APIRouter,Depends,HTTPException,Request,Query
from fastapi.responses import JSONResponse
from .auth import require

router=APIRouter(prefix='/api/v1/history/previous',tags=['Previous conversations'])

def interactive(actor):
    if actor.key_id or actor.auth_source=='integration':raise HTTPException(403,'interactive_session_required')
    return bool(actor.legacy_token and actor.subject.startswith('webui:'))

async def fetch(request,actor,path):
    if not interactive(actor):raise HTTPException(409,'previous_history_not_linked')
    try:
        r=await request.app.state.http.get(request.app.state.settings.legacy_webui+'/api/v1/chats/'+path,
            headers={'Authorization':'Bearer '+actor.legacy_token},timeout=20)
        if r.status_code in (401,403,404):raise HTTPException(404,'chat_not_found')
        r.raise_for_status()
        if len(r.content)>8*1024*1024:raise HTTPException(413,'previous_conversation_too_large')
        return r.json()
    except (httpx.HTTPError,ValueError):raise HTTPException(503,'previous_history_unavailable') from None

def timestamp(value):
    try:return datetime.fromtimestamp(float(value),timezone.utc).isoformat()
    except (ValueError,TypeError,OverflowError):return None

def branch(chat):
    history=chat.get('history') or {};mapping=history.get('messages') or {};current=history.get('currentId')
    messages=[]
    if isinstance(mapping,dict) and mapping and current:
        seen=set()
        while current:
            if current in seen or current not in mapping or len(seen)>=2000:raise HTTPException(409,'previous_history_branch_incomplete')
            seen.add(current);m=mapping[current]
            if not isinstance(m,dict):raise HTTPException(409,'previous_history_branch_incomplete')
            messages.append(m);current=m.get('parentId')
        messages.reverse()
    elif isinstance(chat.get('messages'),list):messages=chat['messages']
    elif mapping:raise HTTPException(409,'previous_history_branch_incomplete')
    result=[]
    for m in messages:
        if not isinstance(m,dict) or m.get('role') not in ('user','assistant'):continue
        content=m.get('content','')
        if isinstance(content,list):content='\n'.join(str(p.get('text','')) for p in content if isinstance(p,dict) and p.get('type')=='text')
        if not isinstance(content,str):raise HTTPException(409,'previous_history_format_unsupported')
        result.append({'role':m['role'],'content':content,'status':'interrupted' if m.get('done') is False and m['role']=='assistant' else 'completed'})
    return result

async def owned(request,actor,identifier):
    row=await fetch(request,actor,str(identifier))
    if not isinstance(row,dict) or str(row.get('user_id'))!=actor.subject.removeprefix('webui:') or str(row.get('id'))!=str(identifier):raise HTTPException(404,'chat_not_found')
    return row

@router.get('')
async def previous(request:Request,page:int=Query(default=1,ge=1,le=10000),archived:bool=False,actor=Depends(require('history.read'))):
    if not interactive(actor):return {'available':False,'items':[],'has_more':False}
    rows=await fetch(request,actor,('archived?page='+str(page) if archived else 'list?page='+str(page)+'&include_pinned=true&include_folders=true'))
    if not isinstance(rows,list):raise HTTPException(503,'previous_history_unavailable')
    items=[]
    for row in rows[:60]:
        try:identifier=str(uuid.UUID(row['id']))
        except (KeyError,TypeError,ValueError):continue
        items.append({'id':identifier,'title':str(row.get('title') or 'Conversa anterior')[:200],'updated_at':timestamp(row.get('updated_at'))})
    return {'available':True,'items':items,'has_more':len(rows)>=60,'page':page}

@router.get('/{identifier}')
async def read(identifier:uuid.UUID,request:Request,actor=Depends(require('history.read'))):
    row=await owned(request,actor,identifier);chat=row.get('chat') or {}
    return {'id':str(identifier),'title':str(row.get('title') or chat.get('title') or 'Conversa anterior')[:200],
        'messages':branch(chat),'updated_at':timestamp(row.get('updated_at')),'read_only':True,
        'notice':'Histórico preservado. Anexos, modelos e permissões antigos não são transferidos automaticamente. Para continuar, crie uma cópia e selecione os documentos autorizados novamente.'}

@router.get('/{identifier}/export')
async def export(identifier:uuid.UUID,request:Request,actor=Depends(require('history.read'))):
    row=await owned(request,actor,identifier);chat=row.get('chat') or {}
    return JSONResponse({'title':row.get('title'),'history':chat.get('history'),'messages':chat.get('messages'),'exported_at':datetime.now(timezone.utc).isoformat()},
        headers={'Content-Disposition':'attachment; filename="moara-conversa-anterior-'+str(identifier)+'.json"','Cache-Control':'no-store'})

@router.post('/{identifier}/resume',status_code=201)
async def resume(identifier:uuid.UUID,request:Request,actor=Depends(require('history.manage'))):
    actor.require('history.read')
    value=await read(identifier,request,actor);messages=value['messages']
    if not messages or len(messages)>100 or any(len(m['content'])>50000 for m in messages) or sum(len(m['content'].encode()) for m in messages)>1024**2:raise HTTPException(413,'previous_conversation_too_large')
    db=request.app.state.db;target=str(uuid.uuid4());base=datetime.now(timezone.utc);crypto=request.app.state.settings.fernet()
    async with db.engine.begin() as conn:
        row=await db.execute('''INSERT INTO moara.chats(id,account_id,title) VALUES(CAST(:id AS uuid),CAST(:owner AS uuid),:title)
            RETURNING id,title,profile_id,updated_at''',{'id':target,'owner':str(actor.user_id),'title':value['title']},one=True,conn=conn)
        for index,m in enumerate(messages):
            await db.execute('''INSERT INTO moara.messages(id,chat_id,role,content,status,created_at)
                VALUES(CAST(:id AS uuid),CAST(:chat AS uuid),:role,:content,:status,:created)''',
                {'id':str(uuid.uuid4()),'chat':target,'role':m['role'],'content':crypto.encrypt(m['content'].encode()).decode(),
                    'status':m['status'],'created':base+timedelta(microseconds=index)},conn=conn)
        await db.audit(actor,'chat.previous.copied',str(identifier)+'->'+target,request_id=request.state.request_id,conn=conn)
    return {**row,'notice':value['notice']}
