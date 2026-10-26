import asyncio
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from moara.gateway import chat_api
from moara.gateway.software_routing import automatic_order

IDS = ('fast', 'general', 'coding', 'qwen25-coder-32b', 'llama31-70b', 'llama33-70b', 'deepseek-coder-v2-lite')

def profiles():
    return [dict(id=i, category='coding' if i in ('coding', 'qwen25-coder-32b', 'deepseek-coder-v2-lite') else 'general',
                 settings={'auto_eligible': True}, manual_allowed=True) for i in IDS]

@pytest.mark.parametrize('prompt,expected', [
    ('Crie uma função Python para somar dois números.', 'deepseek-coder-v2-lite'),
    ('Refatore o código Python e acrescente testes de persistência.', 'qwen25-coder-32b'),
    ('Revise a arquitetura do software e a segurança da API.', 'llama33-70b'),
    ('Planeje a migração de software de um sistema legado.', 'llama31-70b'),
    ('Olá!', 'fast'),
])
def test_task_tiers(prompt, expected):
    ordered, _ = automatic_order(profiles(), [{'role':'user', 'content':prompt}])
    assert ordered[0]['id'] == expected

def test_route_enforces_key_visibility_tools_and_exclusions(monkeypatch):
    visible = profiles()
    async def permitted(db, actor): return visible
    async def candidates(db, profile):
        return [dict(id=profile['id'], capabilities={'completion':True, 'tools':profile['id'] not in ('deepseek-coder-v2-lite','qwen25-coder-32b'), 'structured_output':profile['id']=='coding'})]
    monkeypatch.setattr(chat_api, 'visible_profiles', permitted)
    monkeypatch.setattr(chat_api, 'candidates', candidates)
    async def run():
        body=chat_api.Completion(messages=[{'role':'user','content':'Refatore o código e acrescente testes.'}], tools=[{'type':'function'}])
        p, _, reason=await chat_api.route(None, SimpleNamespace(), body)
        assert p['id']=='coding' and reason.endswith('compatible_fallback')
        p, _, _=await chat_api.route(None, SimpleNamespace(), body.model_copy(update={'tools':None,'response_format':{'type':'json_object'}}))
        assert p['id']=='coding'
        p, _, _=await chat_api.route(None, SimpleNamespace(), body, excluded={'coding'})
        assert p['id'] not in ('coding','qwen25-coder-32b','deepseek-coder-v2-lite')
        visible[:]=[p for p in visible if p['id']=='fast']
        p, _, _=await chat_api.route(None, SimpleNamespace(), body)
        assert p['id']=='fast'
        with pytest.raises(HTTPException) as error:
            await chat_api.route(None, SimpleNamespace(), body.model_copy(update={'model':'llama33-70b'}))
        assert error.value.status_code==403
    asyncio.run(run())

def test_admin_opt_out():
    rows=profiles()
    for p in rows:
        if p['id']=='deepseek-coder-v2-lite':p['settings']['auto_eligible']=False
    ordered,_=automatic_order(rows,[{'role':'user','content':'Crie código Python.'}])
    assert all(p['id']!='deepseek-coder-v2-lite' for p in ordered)
