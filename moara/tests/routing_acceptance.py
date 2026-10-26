"""Isolated real auth/PG with a deliberately mocked unavailable inference server."""
import asyncio
import json
import uuid
from pathlib import Path
import httpx
from moara.gateway.api import create_app
from moara.gateway.settings import Settings

checks={}
def check(name,value):
    checks[name]=bool(value)
    if not value:raise AssertionError(name)

async def main():
    app=create_app(Settings.load())
    async with app.router.lifespan_context(app):
        origin='https://localhost:8443'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=origin+'/moara/api/v1/',headers={'Origin':origin}) as admin:
            logged=await admin.post('auth/login',json={'email':'admin@staging.invalid','password':Path('/run/secrets/admin_password').read_text()})
            check('verified_staging_login',logged.status_code==200);admin.headers['X-Moara-CSRF']=logged.json()['csrf_token']
            check('versioned_profile_contract',(await admin.get('models/profiles')).status_code==200)
            check('versioned_model_metrics_contract',(await admin.get('models/metrics')).status_code==200)
            response=await admin.post('chat/stream',json={'model':'fast','messages':[{'role':'user','content':'Quem é você?'}]})
            check('stream_endpoint_forces_sse',response.status_code==200 and response.headers['content-type'].startswith('text/event-stream') and '[DONE]' in response.text)
            rows=(await admin.get('models')).json();model=rows[0]
            body={'id':'coding','name':'Synthetic compatible fallback','description':'Staging fixture only','category':'coding','enabled':True,
                'manual_allowed':True,'public':False,'allowed_subjects':[],'allowed_groups':[],'model_ids':[model['id']],
                'settings':{'context_length':8192,'threads':12,'temperature':0,'max_tokens':256,'timeout':60,'auto_eligible':True}}
            check('profile_create_real_api',(await admin.post('admin/profiles',json=body)).status_code==201)
            check('profile_duplicate_rejected',(await admin.post('admin/profiles',json=body)).status_code==409)
            # Clone a physical metadata fixture, never an executable production provider.
            mid=str(uuid.uuid4());bid=str(uuid.uuid4())
            await app.state.db.execute('''INSERT INTO moara.models(id,provider,tag,display_name,capabilities,settings)
                VALUES(CAST(:id AS uuid),'fixture','fallback-only','Synthetic alternate',CAST(:caps AS jsonb),'{}')''',
                {'id':mid,'caps':json.dumps({'completion':True,'tools':False})})
            await app.state.db.execute('''INSERT INTO moara.execution_bindings(id,model_id,provider,tag,context_length,threads,ready)
                VALUES(CAST(:id AS uuid),CAST(:model AS uuid),'fixture','fallback-only',8192,12,true)''',{'id':bid,'model':mid})
            await app.state.db.execute("UPDATE moara.profile_models SET model_id=CAST(:id AS uuid) WHERE profile_id='coding'",{'id':mid})
            response=await admin.put('admin/models/'+model['id']+'/activation',json={'active':False})
            check('physical_model_deactivation_real_api',response.status_code==200 and not response.json()['enabled'])
            response=await admin.post('chat/completions',json={'model':'fast','messages':[{'role':'user','content':'Olá.'}]})
            check('disabled_model_not_executable',response.status_code==409)
            response=await admin.put('admin/models/'+model['id']+'/activation',json={'active':True})
            check('preserved_ready_model_can_reactivate',response.status_code==200)
            response=await admin.put('admin/models/'+mid+'/activation',json={'active':True})
            check('unapproved_candidate_cannot_be_activated',response.status_code==409)
            actual=app.state.http
            calls=[];mode={'value':'fallback'}
            def inference(request):
                if request.url.path.endswith('/sources'):
                    return httpx.Response(200,json=[{'name':'Synthetic authorized source','kind':'sqlite','active':True}])
                calls.append(json.loads(request.content))
                if mode['value']=='limited':return httpx.Response(429,json={'detail':'synthetic_rate_limit'})
                if mode['value']=='failed' or mode['value']=='fallback' and len(calls)==1:return httpx.Response(503,json={'detail':'synthetic_unavailable'})
                if mode['value']=='identity':
                    chunks=[{'choices':[{'index':0,'delta':{'content':text},'finish_reason':None}]} for text in ['Eu ','sou ','Gem','ma.']]
                    chunks.append({'choices':[{'index':0,'delta':{},'finish_reason':'stop'}]})
                    stream=''.join('data: '+json.dumps(c)+'\n\n' for c in chunks)+'data: [DONE]\n\n'
                    return httpx.Response(200,content=stream.encode(),headers={'content-type':'text/event-stream'})
                return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'OK'},'finish_reason':'stop'}]})
            async with httpx.AsyncClient(transport=httpx.MockTransport(inference)) as mock:
                app.state.http=mock
                try:
                    response=await admin.post('chat/completions',json={'model':'auto','messages':[{'role':'user','content':'Responda com uma saudação.'}]})
                    check('automatic_provider_failure_recovers',response.status_code==200 and len(calls)==2)
                    check('fallback_uses_other_physical_model',calls[0]['model']!=calls[1]['model'])
                    check('fallback_reason_visible',response.json()['moara']['reason'].endswith(':execution_fallback'))
                    calls.clear();mode['value']='failed'
                    response=await admin.post('chat/completions',json={'model':'fast','messages':[{'role':'user','content':'Olá, teste.'}]})
                    check('manual_profile_never_silently_changes',response.status_code==503 and len(calls)==1)
                    calls.clear();mode['value']='limited'
                    response=await admin.post('chat/completions',json={'model':'auto','messages':[{'role':'user','content':'Olá, teste.'}]})
                    check('rate_limit_never_retried',response.status_code==429 and len(calls)==1)
                    calls.clear();mode['value']='failed'
                    response=await admin.post('chat/completions',json={'model':'auto','messages':[{'role':'user','content':'Olá, teste.'}]})
                    check('fallback_bounded_to_two_attempts',response.status_code==503 and len(calls)==2)
                    calls.clear();mode['value']='parameters'
                    response=await admin.post('chat/completions',json={'model':'fast','messages':[{'role':'user','content':'Teste de transporte dos parâmetros.'}],
                        'max_completion_tokens':77,'top_p':0.8,'seed':42,'stop':['END'],'tools':[{'type':'function','function':{'name':'unused','parameters':{'type':'object','properties':{}}}}],'tool_choice':'none'})
                    check('completion_budget_and_sampling_preserved',response.status_code==200 and calls[0]['max_tokens']==77 and calls[0]['top_p']==0.8 and calls[0]['seed']==42 and calls[0]['stop']==['END'])
                    check('disabled_tools_not_sent_to_non_tool_runner','tools' not in calls[0])
                    calls.clear();mode['value']='identity'
                    response=await admin.post('chat/completions',json={'model':'fast','stream':True,'messages':[{'role':'user','content':'Apresente sua identidade em texto livre.'}]})
                    chunks=[json.loads(line[5:]) for line in response.text.splitlines() if line.startswith('data:') and '[DONE]' not in line]
                    text=''.join(c.get('delta',{}).get('content','') for chunk in chunks for c in chunk.get('choices',[]))
                    identity,_=await app.state.identity.active()
                    check('fragmented_identity_guard_in_actual_api',response.status_code==200 and text==identity.document.presentation and 'sou Gemma' not in text)
                    calls.clear();mode['value']='sources'
                    response=await admin.post('identity/answer',json={'question':'Quais fontes você pode acessar?'})
                    check('canonical_sources_use_live_authorized_metadata',response.status_code==200 and 'Synthetic authorized source' in response.json()['answer'])
                finally:app.state.http=actual
            chat=(await admin.post('chats',json={'title':'Interrupted synthetic answer'})).json()
            body={'title':chat['title'],'profile_id':'fast','expected_updated_at':chat['updated_at'],
                'messages':[{'role':'assistant','content':'Partial fixture response','status':'interrupted'}]}
            response=await admin.put('chats/'+chat['id'],json=body)
            stored=(await admin.get('chats/'+chat['id'])).json()
            check('partial_answer_status_survives_real_storage',response.status_code==200 and stored['messages'][0]['status']=='interrupted')
    return {'passed':True,'checks':checks,'scope':'isolated staging; real API/auth/PostgreSQL; deliberately mocked inference transport only'}

if __name__=='__main__':
    try:report=asyncio.run(main())
    except Exception as error:report={'passed':False,'checks':checks,'failure_type':type(error).__name__}
    print(json.dumps(report));raise SystemExit(0 if report['passed'] else 1)
