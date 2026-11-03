"""Canonical answers use live, permission-filtered platform metadata."""
import json
import httpx
from moara.identity.service import normalize
from .catalog_api import visible_profiles,candidates


async def answer(identity,question,request,actor,model=None,messages=()):
    item=identity.question_item(question)
    if item is None:
        from .self_knowledge import answer as describe_platform
        return await describe_platform(identity,question,request,actor,model,messages)
    sources=[];software=True
    if item.dynamic=='sources' and actor.can('connectors.read') and actor.can('data.query'):
        headers={'Authorization':'Bearer '+request.app.state.settings.connector_key,
                 'X-Actor-Id':actor.subject,'X-Actor-Admin':str(actor.can('connectors.manage')).lower()}
        if actor.allowed_sources is not None:headers['X-Actor-Source-Ids']=json.dumps(list(actor.allowed_sources))
        try:
            result=await request.app.state.http.get(request.app.state.settings.connector_hub+'/v1/sources',headers=headers,timeout=5)
            result.raise_for_status()
            if len(result.content)>4*1024**2:raise ValueError('oversized_metadata')
            sources=[{'name':s['name'],'kind':s['kind']} for s in result.json() if s.get('active') and s.get('verified',True)]
        except (httpx.HTTPError,ValueError,KeyError,TypeError):
            value=identity.resolve(question,model=model)
            value['answer']='Não foi possível verificar as fontes autorizadas nesta sessão agora. Não afirmo acesso a bancos ou sistemas sem essa verificação.'
            return value
    if item.dynamic=='development':
        software=False
        for profile in await visible_profiles(request.app.state.db,actor):
            if profile['category']=='coding' and await candidates(request.app.state.db,profile):software=True;break
    value=identity.resolve(question,model=model,sources=sources,software_available=software)
    if item.id=='scope':
        value['answer']='Minha especialização jurídica e institucional orienta a escolha interna dos assistentes. Também atendo perguntas gerais, sem exigir justificativa de finalidade institucional. Permissões, sigilo, conferência de fontes jurídicas e revisão humana de atos oficiais permanecem sob controle da aplicação.'
    if item.id in ('software','scope','capabilities'):
        value['answer']+=' A Moara Desenvolvedora atende também projetos pessoais, comerciais, educacionais e de entretenimento, sem exigir relação institucional. O acesso às ferramentas continua sujeito às permissões da sessão.'
    if item.dynamic=='sources':
        value['answer']+=' Esta informação trata dos conectores de dados institucionais. Documentos e histórico exigem acesso autorizado. A pesquisa de legislação e jurisprudência em fontes oficiais é uma funcionalidade distinta, sujeita à disponibilidade e à conferência das fontes.'
    return value
