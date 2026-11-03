"""Ground database chat in the authorized catalog and existing read-only planner."""
import asyncio
import json
import re
import time
import unicodedata
import httpx


def data_question(question):
    if not isinstance(question,str) or not question or len(question)>2000:return False
    # Native title/tag/follow-up tasks quote the conversation as input. They
    # must never turn that quoted text into a new database operation.
    if question.lstrip().casefold().startswith('### task:'):return False
    text=''.join(c for c in unicodedata.normalize('NFKD',question.casefold()) if not unicodedata.combining(c))
    if re.search(r'\b(crie|implemente|desenvolva|exemplo|codigo|debug|refatore|escreva|arquivo|workspace|repositorio|python|typescript|javascript|read_file|single_find_and_replace)\b',text):return False
    return bool(re.search(r'\b(secp|oracle|sarh|fontes?|conectores?|bancos? de dados|base[s]? de dados)\b',text)
        or re.search(r'\b(ferias|homologa\w*|marcacoes?|apurac\w*|solicitacoes?|recessos?|jornadas?)\b|banco de horas|horas extras|controle de ponto',text) and re.search(r'\b(quantos|quantas|quanto|qual|quais|total|saldo|liste|lista|mostre|consulte|compare|quem|media|some|soma|distribui\w*)\b',text)
        or re.search(r'\b(contracheques?|holerites?)\b',text)
        or re.search(r'\b(afastad\w*|afastamentos?|licencas?)\b',text) and re.search(r'\b(servidores?|pessoas?|funcionarios?|setor|lotacao|quantos|quantas|liste|lista|mostre|monte|quem)\b',text)
        or re.search(r'\b[A-Za-z_][A-Za-z0-9_$#]*\.[A-Za-z_][A-Za-z0-9_$#]*\b',question) and re.search(r'\b(quantos|quantas|contagem|count|registros|tabela|select|consulte)\b',text)
        or re.search(r'\b(quantos|quantas|liste|quais|consulte|mostre)\b',text) and re.search(r'\b(servidores ativos|servidores inativos|cargos|lotacoes|funcionarios)\b',text)
        or re.search(r'\b(?:sj[a-z]{2}|jfam)\b',text) and re.search(r'\b(quantos|quantas|total|liste|listar|mostre|quais|consulte|consultar|consulta|tabelas?|registros|servidores|cargos)\b',text))


def unavailable(message=None):
    return {'answer':message or 'Não foi possível concluir a consulta autorizada agora. Nenhum resultado foi inferido. Confira a fonte na Central de conectores.',
        'sources':[],'execution_mode':'data_query_unavailable'}

def planner_order(question):
    # All official assistants share the validated principal GPU model. Heavy
    # CPU specialists remain available only as explicit authorized selections.
    return ('general',)

def secp_profile_command(question):
    match=re.fullmatch(r'\s*(?:usar|use|utilize|selecionar|selecione)\s+(?:o\s+)?perfil\s+([A-Za-z0-9_-]{1,80})\s+(?:(?:do|no)\s+)?SECP[.!]?\s*',question,re.I)
    if match:return True,match[1].upper()
    return (bool(re.search(r'\bperfis\b',question,re.I) and re.search(r'\bSECP\b',question,re.I)),None)


async def answer(question,request,actor,*,force=False):
    if request.scope.get('moara_disable_data_tools') or '/internal/connectors/' in request.scope.get('path','') or (not force and not data_question(question)):return None
    personal_portal=bool(re.search(r'\b(contracheques?|holerites?)\b',question,re.I))
    secp=bool(re.search(r'\bsecp\b',question,re.I))
    if secp and getattr(actor,'key_id',None) is not None and not actor.can('data.query'):
        return unavailable('Esta chave de API não possui o escopo data.query para consultar o SECP.')
    if not personal_portal and not secp and (not actor.can('connectors.read') or not actor.can('data.query')):
        return unavailable('Sua sessão não possui permissão para consultar as fontes de dados. Solicite ao administrador a liberação da conta ou da chave de API; nenhuma consulta foi executada.')
    from .connector_tickets import issue
    headers={'Authorization':'Bearer '+request.app.state.settings.connector_key,
        'X-Actor-Id':actor.subject,'X-Actor-Admin':str(actor.can('connectors.manage')).lower(),
        'X-Moara-Execution-Ticket':await issue(request,actor,secp=secp)}
    if actor.allowed_sources is not None:headers['X-Actor-Source-Ids']=json.dumps(list(actor.allowed_sources))
    client=request.app.state.http;base=request.app.state.settings.connector_hub+'/v1'
    run_id=None;finished=False
    try:
        profile_request,profile=secp_profile_command(question)
        if profile_request:
            if profile and getattr(actor,'key_id',None) is not None:return unavailable('Selecione o perfil do SECP na sua sessão pessoal; uma chave de API não altera o perfil da conta.')
            response=await client.post(base+'/secp/access',headers=headers,json={'profile':profile},timeout=45)
            if response.status_code!=200:return unavailable(str(response.json().get('detail','Não foi possível consultar os perfis do SECP'))[:600])
            value=response.json();active=value['access']['profile']
            if profile:
                await request.app.state.db.execute("UPDATE moara.accounts SET preferences=jsonb_set(coalesce(preferences,'{}'::jsonb),'{secp_profile}',CAST(:profile AS jsonb)),updated_at=now() WHERE id=CAST(:id AS uuid)",{'profile':json.dumps(active),'id':str(actor.user_id)})
                await request.app.state.db.audit(actor,'secp.profile.selected',active)
                text='Perfil **'+active+'** do SECP selecionado. As próximas consultas usarão suas permissões atuais desse perfil.'
            else:
                configured=value.get('configured_profile') or active
                label='Perfil selecionado: **'+configured+'**. ' if any(p['code']==configured for p in value['profiles']) else 'O perfil anteriormente selecionado não está mais atribuído. '
                text=label+'Perfis do SECP atribuídos à sua conta: '+', '.join(p['code'] for p in value['profiles'])+'. Para selecionar um deles, envie “Usar perfil CODIGO no SECP”.'
            return {'answer':text,'sources':[],'execution_mode':'secp_profile_selected' if profile else 'secp_profiles','handled':True}
        response=await client.post(base+'/quick-answer',headers=headers,json={'question':question},timeout=httpx.Timeout(110,connect=5))
        if response.status_code!=200:return unavailable(str(response.json().get('detail','Não foi possível consultar o SECP'))[:600] if secp else None)
        value=response.json()
        if value.get('handled'):return value
        # Reuse the bounded queue, source ACLs, read-only validator and audit.
        # Delegated inference must use an installed, permitted, validated planner.
        from .catalog_api import visible_profiles,candidates
        profiles=await visible_profiles(request.app.state.db,actor);planner=None
        for identifier in planner_order(question):
            p=next((p for p in profiles if p['id']==identifier and p['manual_allowed']),None)
            if p and any(m['capabilities'].get('tools') for m in await candidates(request.app.state.db,p)):
                planner=identifier;break
        if planner is None:return unavailable('Não há modelo de planejamento com ferramentas autorizado nesta sessão. O administrador deve liberar um perfil compatível para consultar os dados.')
        headers['X-Moara-Execution-Ticket']=await issue(request,actor,planner,secp=secp)
        response=await client.post(base+'/ask',headers=headers,json={'question':question,'model':planner},timeout=15)
        if response.status_code!=200:return unavailable('A consulta não pôde entrar na fila autorizada. Verifique a fonte e tente novamente; nenhum resultado foi inferido.')
        run_id=response.json()['id'];deadline=time.monotonic()+360
        while time.monotonic()<deadline:
            if await request.is_disconnected():return unavailable('Consulta interrompida pelo cliente.')
            response=await client.get(base+'/runs/'+run_id,headers=headers,timeout=15)
            if response.status_code!=200:return unavailable()
            run=response.json()
            if run['status']=='completed':
                finished=True;result=run['result']
                return {'answer':result['answer'],'sources':result.get('sources',[]),
                    'execution_mode':result.get('execution_mode','llm_planned'),
                    'inference_used':result.get('execution_mode')!='validated_count','run_id':run_id}
            if run['status'] in ('failed','cancelled'):
                finished=True
                return unavailable('A consulta foi interrompida pela validação ou pelo conector: '+str(run.get('error') or 'execução cancelada')[:500]+'. Nenhum resultado foi inferido.')
            await asyncio.sleep(0.5)
        return unavailable('A consulta excedeu o prazo do chat e foi cancelada. Tente uma pergunta mais específica pela Central de conectores.')
    except (httpx.HTTPError,ValueError,KeyError,TypeError):return unavailable()
    finally:
        if run_id and not finished:
            try:await asyncio.shield(client.post(base+'/runs/'+run_id+'/cancel',headers=headers,json={},timeout=5))
            except httpx.HTTPError:pass
