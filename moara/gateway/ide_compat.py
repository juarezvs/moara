"""Text Chat Completions compatibility for IDE clients, keeping central policy."""
from fastapi import HTTPException
MODEL='moara-code'

def normalize_messages(messages):
    result=[]
    for item in messages:
        value=dict(item)
        if value.get('role')=='developer':value['role']='system'
        content=value.get('content')
        if isinstance(content,list):
            if any(not isinstance(p,dict) or p.get('type')!='text' or not isinstance(p.get('text'),str) for p in content):
                raise HTTPException(422,'text_chat_required_use_vision_endpoint')
            value['content']='\n'.join(p['text'] for p in content)
        result.append(value)
    return result

def prepare(body,actor):
    body.messages=normalize_messages(body.messages)
    if body.model==MODEL:
        actor.require('development.use')
        if body.assistant_id not in ('auto','desenvolvedora'):raise HTTPException(422,'developer_assistant_required')
        body.model='general';body.assistant_id='desenvolvedora'
    return body

def is_compat(request):
    path=request.url.path
    return path=='/v1' or path.startswith('/v1/') or path.startswith('/moara/v1/')

def error_body(status,detail):
    code=detail if isinstance(detail,str) else 'invalid_request'
    kind='authentication_error' if status==401 else 'permission_error' if status==403 else 'rate_limit_error' if status==429 else 'invalid_request_error' if status<500 else 'server_error'
    return {'error':{'message':code,'type':kind,'param':None,'code':code}}
