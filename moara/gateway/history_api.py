"""Owner-isolated history for new Moara conversations. Legacy history is retained."""
import uuid
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from .auth import require
router=APIRouter(prefix='/api/v1/chats',tags=['Conversation history'])
class NewChat(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title:str=Field(default='Novo chat',min_length=1,max_length=200)
class Message(BaseModel):
    model_config=ConfigDict(extra='forbid')
    role:str=Field(pattern='^(user|assistant)$')
    content:str=Field(max_length=50000)
    status:Literal['completed','interrupted']='completed'
class SaveChat(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title:str=Field(min_length=1,max_length=200)
    profile_id:str=Field(min_length=1,max_length=64)
    expected_updated_at:str=Field(max_length=50)
    messages:list[Message]=Field(max_length=100)

async def owned(db,actor,identifier,conn=None,lock=False):
    row=await db.execute('SELECT * FROM moara.chats WHERE id=CAST(:id AS uuid) AND account_id=CAST(:account AS uuid)'+(' FOR UPDATE' if lock else ''),
        {'id':str(identifier),'account':str(actor.user_id)},one=True,conn=conn)
    if not row:raise HTTPException(404,'chat_not_found')
    return row

@router.get('')
async def list_chats(request:Request,actor=Depends(require('history.read'))):
    return await request.app.state.db.execute('''SELECT id,title,profile_id,pinned,archived,created_at,updated_at FROM moara.chats
        WHERE account_id=CAST(:id AS uuid) ORDER BY pinned DESC,updated_at DESC LIMIT 100''',{'id':str(actor.user_id)})

@router.post('',status_code=201)
async def create_chat(body:NewChat,request:Request,actor=Depends(require('history.manage'))):
    return await request.app.state.db.execute('''INSERT INTO moara.chats(id,account_id,title) VALUES(CAST(:id AS uuid),CAST(:account AS uuid),:title)
        RETURNING id,title,profile_id,updated_at''',{'id':str(uuid.uuid4()),'account':str(actor.user_id),'title':body.title},one=True)

@router.get('/{identifier}')
async def read_chat(identifier:uuid.UUID,request:Request,actor=Depends(require('history.read'))):
    db=request.app.state.db;row=await owned(db,actor,identifier)
    messages=await db.execute('SELECT role,content,status FROM moara.messages WHERE chat_id=CAST(:id AS uuid) ORDER BY created_at,id',{'id':str(identifier)})
    try:
        for m in messages:m['content']=request.app.state.settings.fernet().decrypt(m['content'].encode()).decode()
    except Exception:raise HTTPException(503,'history_integrity_failure') from None
    return {**row,'messages':messages}

@router.put('/{identifier}')
async def save_chat(identifier:uuid.UUID,body:SaveChat,request:Request,actor=Depends(require('history.manage'))):
    if sum(len(m.content.encode()) for m in body.messages)>1024**2:raise HTTPException(413,'conversation_too_large')
    db=request.app.state.db
    async with db.engine.begin() as conn:
        row=await owned(db,actor,identifier,conn,True)
        from datetime import datetime,timedelta,timezone
        try:expected=datetime.fromisoformat(body.expected_updated_at.replace('Z','+00:00'))
        except ValueError:raise HTTPException(422,'invalid_history_version') from None
        if expected!=row['updated_at']:raise HTTPException(409,'conversation_changed')
        await db.execute('DELETE FROM moara.messages WHERE chat_id=CAST(:id AS uuid)',{'id':str(identifier)},conn=conn)
        base=datetime.now(timezone.utc);crypto=request.app.state.settings.fernet()
        for index,m in enumerate(body.messages):
            await db.execute('''INSERT INTO moara.messages(id,chat_id,role,content,status,created_at)
                VALUES(CAST(:id AS uuid),CAST(:chat AS uuid),:role,:content,:status,:created)''',{'id':str(uuid.uuid4()),'chat':str(identifier),
                    'role':m.role,'content':crypto.encrypt(m.content.encode()).decode(),'status':m.status,'created':base+timedelta(microseconds=index)},conn=conn)
        result=await db.execute('''UPDATE moara.chats SET title=:title,profile_id=:profile,updated_at=clock_timestamp() WHERE id=CAST(:id AS uuid)
            RETURNING id,updated_at''',{'id':str(identifier),'title':body.title,'profile':body.profile_id},one=True,conn=conn)
    return result

@router.delete('/{identifier}')
async def delete_chat(identifier:uuid.UUID,request:Request,actor=Depends(require('history.manage'))):
    db=request.app.state.db
    async with db.engine.begin() as conn:
        await owned(db,actor,identifier,conn,True)
        await db.execute('DELETE FROM moara.chats WHERE id=CAST(:id AS uuid)',{'id':str(identifier)},conn=conn)
        await db.audit(actor,'chat.delete',identifier,request_id=request.state.request_id,conn=conn)
    return {'deleted':True}
