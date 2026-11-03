"""Moara routing and OpenAI-compatible inference through the bounded CPU adapter."""
import asyncio
import json
import re
import time
import uuid
from datetime import datetime,timezone
from typing import Literal
from uuid import UUID
import httpx
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import JSONResponse,StreamingResponse
from pydantic import BaseModel,ConfigDict,Field
from moara.identity.service import compose_prompt
from moara.identity.stream import IdentityPrefixGuard
from .auth import require
from .catalog_api import visible_profiles,candidates
from .chat_progress import publish

router=APIRouter(tags=['Chat'])

class Completion(BaseModel):
    model_config=ConfigDict(extra='allow')
    model:str=Field(default='auto',min_length=1,max_length=128)
    messages:list[dict]=Field(min_length=1,max_length=100)
    stream:bool=False
    tools:list[dict]|None=Field(default=None,max_length=32)
    max_tokens:int|None=Field(default=None,ge=1,le=4096)
    max_completion_tokens:int|None=Field(default=None,ge=1,le=4096)
    temperature:float|None=Field(default=None,ge=0,le=2)
    tool_choice:str|dict|None=None
    response_format:dict|None=None
    reasoning_effort:str|None=None
    top_p:float|None=Field(default=None,ge=0,le=1)
    seed:int|None=None
    stop:str|list[str]|None=None
    frequency_penalty:float|None=Field(default=None,ge=-2,le=2)
    presence_penalty:float|None=Field(default=None,ge=-2,le=2)
    parallel_tool_calls:bool|None=None
    stream_options:dict|None=None
    legal_context:dict|None=None
    assistant_id:Literal['auto','juridica','gabinete','administrativa','documental','desenvolvedora','dados']='auto'
    document_ids:list[UUID]=Field(default_factory=list,max_length=16)

async def route(db,actor,body,excluded=()):
    profiles=await visible_profiles(db,actor)
    if body.model!='auto':
        profile=next((p for p in profiles if p['id']==body.model),None)
        if not profile:raise HTTPException(403,'profile_not_authorized')
        if not profile['manual_allowed']:raise HTTPException(403,'manual_selection_disabled')
        reason='manual_authorized';ordered=[profile]
    else:
        from .software_routing import automatic_order
        ordered,reason=automatic_order(profiles,body.messages)
    # A tool catalog is a real capability requirement, even when tool_choice=auto.
    needs_tools=bool(body.tools) and body.tool_choice!='none'
    for profile in ordered:
        for model in await candidates(db,profile):
            if str(model['id']) in excluded:continue
            if not model['capabilities'].get('completion'):continue
            if needs_tools and not model['capabilities'].get('tools'):continue
            if body.response_format and not model['capabilities'].get('structured_output'):continue
            return profile,model,reason if ordered[0]['id']==profile['id'] else reason+':compatible_fallback'
    raise HTTPException(409,'no_compatible_execution_available')

def validate_messages(messages):
    for m in messages:
        if m.get('role') not in ('system','user','assistant','tool'):raise HTTPException(422,'invalid_message_role')
        content=m.get('content')
        if content is not None and not isinstance(content,str):raise HTTPException(422,'text_chat_required_use_vision_endpoint')
        if m.get('role')=='tool' and not isinstance(m.get('tool_call_id'),str):raise HTTPException(422,'tool_call_id_required')
    if sum(len(json.dumps(m,ensure_ascii=False)) for m in messages)>200000:raise HTTPException(413,'conversation_too_large')

def sse(value):return 'data: '+json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n\n'

async def record(db,actor,rid,profile,model,reason,stream,identity,status,duration,ttft=None,usage=None,error=None):
    usage=usage or {}
    await db.execute('''INSERT INTO moara.requests(id,account_id,api_key_id,profile_id,model_id,routing_reason,status,stream,identity_version,
        duration_ms,ttft_ms,prompt_tokens,completion_tokens,error_code) VALUES(CAST(:id AS uuid),CAST(:actor AS uuid),CAST(:key AS uuid),:profile,
        CAST(:model AS uuid),:reason,:status,:stream,:identity,:duration,:ttft,:prompt,:completion,:error)''',
        {'id':str(rid),'actor':str(actor.user_id),'key':str(actor.key_id) if actor.key_id else None,'profile':profile['id'],
            'model':str(model['id']) if status!='canonical' else None,'reason':reason,'status':status,'stream':stream,'identity':identity.document.version,
            'duration':duration,'ttft':ttft,'prompt':usage.get('prompt_tokens'),'completion':usage.get('completion_tokens'),'error':error})

@router.post('/api/v1/chat/completions')
@router.post('/v1/chat/completions')
async def completion(body:Completion,request:Request,actor=Depends(require('chat.use'))):
    ide_model=body.model=='moara-code'
    from .ide_compat import prepare as prepare_ide
    body=prepare_ide(body,actor)
    validate_messages(body.messages)
    if body.document_ids and body.tools and body.tool_choice!='none':raise HTTPException(422,'document_analysis_uses_application_tools')
    db=request.app.state.db;started=time.monotonic();rid=uuid.uuid4()
    automatic_model=body.model=='auto'
    identity,_=await request.app.state.identity.active()
    from .client_documents import split_questions,SOURCE_INSTRUCTION as INLINE_SOURCE_INSTRUCTION,validate as validate_inline_sources
    policy_messages,inline_context=split_questions(body.messages,actor)
    last=policy_messages[-1]
    canonical=None
    canonical_kind='institutional_identity'
    from .legal_verification import preflight as legal_preflight,SELECTION_CAPABILITY
    selection_only=request.scope.get('_moara_legal_selection') is SELECTION_CAPABILITY
    from .legal_answer import RESEARCH_CAPABILITY
    research_only=request.scope.get('_moara_legal_research') is RESEARCH_CAPABILITY
    from .orchestration import CLASSIFICATION_CAPABILITY,FINITE_RANKING_CAPABILITY,PLATFORM_CONTEXT_CAPABILITY,prepare,assert_tool,for_tool,requires_data_execution
    classification_only=request.scope.get('_moara_intent_classification') is CLASSIFICATION_CAPABILITY
    ranking_only=request.scope.get('_moara_finite_ranking') is FINITE_RANKING_CAPABILITY
    from .web_research import CAPABILITY as WEB_CAPABILITY
    web_only=request.scope.get('_moara_web_research') is WEB_CAPABILITY
    internal_task=selection_only or research_only or classification_only or ranking_only or web_only
    assistant=None;identity_question=False
    if not internal_task:
        publish(request,'analyzing_request')
        assistant,canonical,identity_question=await prepare(body,request,actor,identity,rid,policy_messages,inline_context is not None)
        if canonical is not None:canonical_kind='institutional_policy'
        if canonical is None and not identity_question and (body.legal_context or assistant and assistant['requires_legal_sources']):
            publish(request,'preparing_legal_check')
            if assistant:await for_tool(assistant,actor,'normas.read',request,rid)
            canonical=await legal_preflight(policy_messages,request,actor,body.legal_context,force=True)
            if canonical is not None:canonical_kind='legal_verification'
    profile,model,reason=await route(db,actor,body.model_copy(update={'messages':policy_messages}) if inline_context else body)
    if assistant and automatic_model:reason='assistant_shared_principal'
    if not internal_task and canonical is None and last.get('role')=='user' and not body.response_format and body.tool_choice not in ('required',) and not isinstance(body.tool_choice,dict):
        from .data_chat import answer as data_answer
        if assistant and assistant['id']=='dados' and requires_data_execution(last.get('content','')):
            assert_tool(assistant,actor,'data.read')
            if body.document_ids:
                canonical={'answer':'Para calcular indicadores sobre os arquivos, defina no módulo Indicadores do espaço de trabalho a operação, a coluna e os filtros. Não vou apresentar uma contagem ou cálculo inferido de trechos parciais.',
                           'sources':[],'execution_mode':'structured_document_calculation_required','inference_used':False}
            else:
                publish(request,'querying_data')
                canonical=await data_answer(last.get('content',''),request,actor,force=True)
                if canonical is None:canonical={'answer':'Nenhuma consulta de dados foi executada nesta operação. Não vou inferir números ou resultados institucionais. Utilize uma fonte e uma operação autorizadas.',
                                              'sources':[],'execution_mode':'data_execution_required','inference_used':False}
        if canonical is not None:canonical_kind='authorized_data_query'
        from .institutional import answer as resolve
        if canonical is None:canonical=await resolve(identity,last.get('content',''),request,actor,model=model['display_name'],messages=policy_messages)
    matches=[]
    platform_context=request.scope.get('_moara_platform_context',{})
    supplied_authorized_sources=platform_context.get('capability') is PLATFORM_CONTEXT_CAPABILITY and platform_context.get('has_authorized_sources')
    if not internal_task and not supplied_authorized_sources and assistant and canonical is None:
        from .chat_evidence import retrieve
        matches,canonical=await retrieve(body,request,actor,assistant,rid,inline_context is not None)
        if canonical is not None:canonical_kind='institutional_policy'
    if not internal_task and canonical is None and not body.tools and not body.response_format and not body.document_ids and not inline_context and not supplied_authorized_sources:
        from .web_research import answer as web_answer
        canonical=await web_answer(last.get('content',''),request,actor)
        if canonical is not None:
            canonical_kind='web_research'
            from .legal_verification import guard_candidate
            guarded_web=await guard_candidate(canonical['answer'],policy_messages,request,actor,assistant,rid)
            if guarded_web is not None:
                canonical={**guarded_web,'web_research':canonical['web_research']};canonical_kind='legal_verification'
    metadata={'request_id':str(rid),'profile':profile['id'],'model_id':str(model['id']),
        'model_name':model['display_name'],'reason':reason,'identity_version':identity.document.version,'inference_used':canonical is None}
    if assistant:metadata['assistant']=assistant['public']
    if any('<context>' in str(m.get('content') or '') for m in body.messages):
        from .client_documents import PATTERN
        metadata['attachment_input_diagnostics']={'upstream_client':actor.upstream_client_id,
            'legacy_session':bool(actor.legacy_token),
            'messages':[{'role':m.get('role'),'bytes':len(str(m.get('content') or '').encode()),
                'context_blocks':str(m.get('content') or '').count('<context>'),
                'question_blocks':str(m.get('content') or '').count('<moara_user_query>'),
                'recognized_wrapper':bool(PATTERN.fullmatch(str(m.get('content') or '')))} for m in body.messages]}
    if canonical:
        if canonical.get('web_research'):
            metadata['web_research']=canonical['web_research'];metadata['inference_used']=canonical['web_research'].get('inference_used',False)
        if canonical.get('self_knowledge'):metadata['self_knowledge']=canonical['self_knowledge']
        metadata['model_id']=None;metadata['model_name']=None
        metadata['reason']=canonical_kind
        if canonical_kind=='legal_verification':metadata['legal_verification']=canonical['legal_verification'];metadata['inference_used']=canonical['legal_verification'].get('inference_used',False)
        if canonical_kind=='institutional_policy':metadata['policy']=canonical['policy'];metadata['inference_used']=False
        if canonical_kind=='authorized_data_query':metadata.update(data_sources=canonical.get('sources',[]),execution_mode=canonical.get('execution_mode'),inference_used=canonical.get('inference_used',False),data_run_id=canonical.get('run_id'))
        await record(db,actor,rid,profile,model,canonical_kind,body.stream,identity,'canonical',round((time.monotonic()-started)*1000))
        result={'id':'chatcmpl-'+rid.hex,'object':'chat.completion','created':int(time.time()),'model':{'authorized_data_query':'moara-data','legal_verification':'moara-legal','institutional_policy':'moara-policy','web_research':'moara-web'}.get(canonical_kind,'moara-identity'),
            'choices':[{'index':0,'message':{'role':'assistant','content':canonical['answer']},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0},'moara':metadata}
        if ide_model:result['model']='moara-code'
        if not body.stream:return result
        from .chat_delivery import approved_stream
        return StreamingResponse(approved_stream(result),media_type='text/event-stream',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
    from .chat_evidence import compose as compose_evidence,SOURCE_INSTRUCTION,source_metadata
    instruction=assistant['instructions'] if assistant else ''
    if assistant:instruction+='\nAo produzir orientações gerais ou estruturas documentais sem conferência normativa concluída, use campos de fundamentação a conferir. Não acrescente números de leis, precedentes ou afirmações de vigência por memória do modelo.'
    if matches:instruction+='\n'+SOURCE_INSTRUCTION;metadata.update(document_sources=source_metadata(matches),execution_mode='buffered_citation_validation')
    if inline_context:instruction+='\n'+INLINE_SOURCE_INSTRUCTION;metadata['document_context']=inline_context
    messages=compose_prompt(identity,compose_evidence(body.messages,matches),instruction,development=bool(assistant and assistant['id']=='desenvolvedora'))
    maximum=body.max_tokens or body.max_completion_tokens or profile['settings'].get('max_tokens',512)
    from .context_budget import fit as fit_context,input_size,prefix_notice
    attached_context=bool(matches) or any(re.search(r'<(?:source|context)\b',str(m.get('content') or ''),re.I) for m in body.messages)
    messages,maximum,context_info,context_notice=fit_context(messages,body.tools,model['context_length'],maximum,attached_context)
    metadata['context_management']=context_info
    # Internal structured tasks consume JSON, not chat prose. Keep the budget
    # adjustment in audit/metadata without corrupting that machine contract.
    if internal_task and body.response_format:context_notice=''
    if context_notice:
        await db.audit(actor,'context.budget_adjusted','omitted_messages='+str(context_info['omitted_messages'])+';output_limit='+str(maximum),request_id=rid)
    size=input_size(messages,body.tools)
    payload=body.model_dump(exclude_none=True)
    # Ignore unknown client fields instead of passing execution/transport options through.
    payload={k:v for k,v in payload.items() if k in {'stream','tools','tool_choice','response_format','temperature','max_tokens',
        'top_p','seed','stop','frequency_penalty','presence_penalty','parallel_tool_calls','stream_options'}}
    if body.tool_choice=='none':payload.pop('tools',None)
    payload.update(model=model['legacy_alias'] or 'binding:'+str(model['binding_id']),messages=messages,max_tokens=maximum,
        temperature=body.temperature if body.temperature is not None else profile['settings'].get('temperature',0.2))
    # Portal answers are checked before delivery, including unsolicited legal
    # references. Native IDE tool streams keep their transport; explicit legal
    # references in their input already went through application preflight.
    guarded=bool(assistant and not ide_model)
    buffered=bool(matches) or bool(inline_context) or guarded
    if buffered:payload['stream']=False
    if profile['settings'].get('reasoning_effort'):payload['reasoning_effort']=profile['settings']['reasoning_effort']
    elif (model.get('family') or '').casefold().startswith('gemma4'):payload['reasoning_effort']='none'
    timeout=httpx.Timeout(float(profile['settings'].get('timeout',300)),connect=5)
    client=request.app.state.http
    direct_key=actor.upstream_key if model['legacy_alias'] else None
    headers={'Authorization':'Bearer '+(direct_key or request.app.state.settings.llm_key),'X-Request-ID':str(rid)}
    if not direct_key and actor.upstream_client_id:headers['X-Moara-Delegated-Client']=actor.upstream_client_id
    from opentelemetry.propagate import inject
    inject(headers)
    upstream=client.build_request('POST',request.app.state.settings.legacy_gateway+'/v1/chat/completions',json=payload,headers=headers,timeout=timeout)
    if not internal_task:publish(request,'generating_response')
    try:response=await client.send(upstream,stream=body.stream and not buffered)
    except httpx.HTTPError:response=None
    # One compatible alternative is allowed only in automatic mode, before any
    # output is delivered. Never retry rate limits, invalid inputs or tool errors.
    if body.model=='auto' and (response is None or response.status_code in (502,503,504)):
        if response is not None:await response.aclose()
        try:alternate,alternative,new_reason=await route(db,actor,body,{str(model['id'])})
        except HTTPException:alternate=None
        if alternate is not None:
            alternative_max=body.max_tokens or body.max_completion_tokens or alternate['settings'].get('max_tokens',512)
            if size<=max(1024,(alternative['context_length']-alternative_max)*3):
                prior=profile['id'];profile,model=alternate,alternative;reason=new_reason+':execution_fallback'
                metadata.update(profile=profile['id'],model_id=str(model['id']),model_name=model['display_name'],reason=reason,
                    fallback_from=prior)
                payload.update(model=model['legacy_alias'] or 'binding:'+str(model['binding_id']),max_tokens=alternative_max,
                    temperature=body.temperature if body.temperature is not None else profile['settings'].get('temperature',0.2))
                payload.pop('reasoning_effort',None)
                if profile['settings'].get('reasoning_effort'):payload['reasoning_effort']=profile['settings']['reasoning_effort']
                elif (model.get('family') or '').casefold().startswith('gemma4'):payload['reasoning_effort']='none'
                direct_key=actor.upstream_key if model['legacy_alias'] else None
                headers['Authorization']='Bearer '+(direct_key or request.app.state.settings.llm_key)
                headers.pop('X-Moara-Delegated-Client',None)
                if not direct_key and actor.upstream_client_id:headers['X-Moara-Delegated-Client']=actor.upstream_client_id
                timeout=httpx.Timeout(float(profile['settings'].get('timeout',300)),connect=5)
                upstream=client.build_request('POST',request.app.state.settings.legacy_gateway+'/v1/chat/completions',json=payload,headers=headers,timeout=timeout)
                await db.audit(actor,'routing.fallback',profile['id'],request_id=rid)
                try:response=await client.send(upstream,stream=body.stream and not buffered)
                except httpx.HTTPError:response=None
    if response is None:
        await record(db,actor,rid,profile,model,reason,body.stream,identity,'error',round((time.monotonic()-started)*1000),error='inference_unavailable')
        raise HTTPException(503,'inference_unavailable') from None
    if response.status_code!=200:
        status=response.status_code if response.status_code in (400,413,422,429,503,504) else 502
        await response.aclose()
        await record(db,actor,rid,profile,model,reason,body.stream,identity,'error',round((time.monotonic()-started)*1000),error='inference_rejected')
        raise HTTPException(status,'inference_rejected')
    backend=response.headers.get('x-moara-inference-backend')
    if backend in ('gpu','cpu','cpu-fallback'):
        metadata['execution_backend']=backend
        if backend=='cpu-fallback':reason+=':cpu_fallback';metadata['reason']=reason
    if buffered:
        if not internal_task:publish(request,'checking_response')
        from .chat_evidence import finalize_guarded
        try:result=response.json()
        finally:await response.aclose()
        result['moara']=metadata
        result=await finalize_guarded(result,matches,policy_messages,request,actor,assistant,rid,identity)
        result=validate_inline_sources(result,inline_context)
        result=prefix_notice(result,context_notice)
        await record(db,actor,rid,profile,model,reason,body.stream,identity,'completed',round((time.monotonic()-started)*1000),usage=result.get('usage'))
        if not body.stream:return JSONResponse(result)
        from .chat_delivery import approved_stream
        return StreamingResponse(approved_stream(result),media_type='text/event-stream',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
    if not body.stream:
        try:result=response.json()
        finally:await response.aclose()
        if ide_model:result['model']='moara-code'
        for choice in result.get('choices',[]):
            content=choice.get('message',{}).get('content')
            if isinstance(content,str) and identity.rejects_self_identification(content):
                choice['message']['content']=identity.document.presentation
                metadata['identity_guard_applied']=True
        result['moara']=metadata
        result=prefix_notice(result,context_notice)
        await record(db,actor,rid,profile,model,reason,False,identity,'completed',round((time.monotonic()-started)*1000),usage=result.get('usage'))
        return JSONResponse(result)
    async def stream():
        state='completed';ttft=None;usage={};finished=False
        created=int(time.time())
        guard=IdentityPrefixGuard(identity)
        try:
            yield sse({'id':'chatcmpl-'+rid.hex,'object':'chat.completion.chunk','created':created,'model':'moara-code' if ide_model else body.model,'moara':metadata,'choices':[]})
            if context_notice:yield sse({'object':'chat.completion.chunk','choices':[{'index':0,'delta':{'content':context_notice},'finish_reason':None}]})
            async for line in response.aiter_lines():
                if await request.is_disconnected():state='cancelled';break
                if not line.startswith('data:'):continue
                data=line[5:].strip()
                if data=='[DONE]':
                    for value in guard.flush():
                        if ide_model:value.update(id='chatcmpl-'+rid.hex,object='chat.completion.chunk',created=created,model='moara-code')
                        yield sse(value)
                    finished=True;yield 'data: [DONE]\n\n';break
                try:chunk=json.loads(data)
                except ValueError:continue
                if chunk.get('usage'):usage=chunk['usage']
                for value in guard.push(chunk):
                    if ide_model:value.update(id='chatcmpl-'+rid.hex,object='chat.completion.chunk',created=created,model='moara-code')
                    if ttft is None and any(c.get('delta',{}).get('content') or c.get('delta',{}).get('tool_calls') for c in value.get('choices',[])):
                        ttft=round((time.monotonic()-started)*1000)
                    yield sse(value)
            if state=='completed' and not finished:
                state='error';yield sse({'error':{'code':'inference_stream_incomplete','message':'A resposta foi interrompida. Tente novamente.'}})
        except asyncio.CancelledError:state='cancelled';raise
        except httpx.HTTPError:
            state='error';yield sse({'error':{'code':'inference_stream_error','message':'A conexão com o modelo foi interrompida.'}})
        finally:
            await response.aclose()
            # Shield metadata persistence from transport cancellation; never store prompt content here.
            await asyncio.shield(record(db,actor,rid,profile,model,reason,True,identity,state,round((time.monotonic()-started)*1000),ttft,usage))
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'X-Accel-Buffering':'no'})

@router.post('/api/v1/chat/stream')
async def completion_stream(body:Completion,request:Request,actor=Depends(require('chat.use'))):
    # Structural input failures retain their normal HTTP status before SSE opens.
    validate_messages(body.messages)
    from .chat_progress import with_progress
    return with_progress(request,lambda:completion(body.model_copy(update={'stream':True}),request,actor))

@router.get('/api/v1/status')
async def status(request:Request,actor=Depends(require('status.read'))):
    db=request.app.state.db
    counts=await db.execute('''SELECT (SELECT count(*) FROM moara.models WHERE installed) AS installed_models,
        (SELECT count(*) FROM moara.profiles WHERE enabled) AS enabled_profiles,
        (SELECT count(*) FROM moara.accounts WHERE active) AS active_accounts''',one=True)
    metrics=await db.execute('''SELECT status,count(*) AS requests,percentile_cont(0.5) WITHIN GROUP(ORDER BY duration_ms) AS p50_ms,
        percentile_cont(0.95) WITHIN GROUP(ORDER BY duration_ms) AS p95_ms,
        percentile_cont(0.99) WITHIN GROUP(ORDER BY duration_ms) AS p99_ms FROM moara.requests
        WHERE created_at>now()-interval '24 hours' GROUP BY status''')
    from redis.asyncio import Redis
    async with Redis.from_url(request.app.state.settings.redis_url(1),socket_timeout=3) as redis:
        worker=await redis.get('moara:worker:presence')
    return {'counts':counts,'requests_last_24h':metrics,'percentiles_scope':'observed requests, no statistical confidence claim','legacy_chat_retained':True,'worker_available':bool(worker)}
