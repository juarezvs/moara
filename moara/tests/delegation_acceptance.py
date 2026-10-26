"""Real staging PG/Redis/auth/ASGI delegation; the hub transport alone is mocked.

No production source or model is contacted. Secrets remain in process memory.
"""
import asyncio
import json
import uuid
from pathlib import Path
from starlette.requests import Request
import httpx
from moara.gateway.api import create_app
from moara.gateway import connector_tickets
from moara.gateway.settings import Settings

checks=[]
def check(name,value):
    checks.append({'name':name,'passed':bool(value)})
    if not value:raise AssertionError(name)

async def main():
    config=Settings.load();app=create_app(config)
    async with app.router.lifespan_context(app):
        transport=httpx.ASGITransport(app=app);origin='https://localhost:8443';base=origin+'/moara/api/v1/'
        async with httpx.AsyncClient(transport=transport,base_url=base,headers={'Origin':origin}) as admin:
            logged=await admin.post('auth/login',json={'email':'admin@staging.invalid','password':Path('/run/secrets/admin_password').read_text()})
            check('delegation_admin_login',logged.status_code==200);admin.headers['X-Moara-CSRF']=logged.json()['csrf_token']
            created=await admin.post('admin/accounts',json={'name':'Delegation synthetic fixture','email':'delegation@staging.invalid','roles':['user']})
            check('delegation_owner_created',created.status_code==201);owner=created.json()['id'];allowed=str(uuid.uuid4())
            issued=await admin.post('admin/api-keys',json={'account_id':owner,'name':'Delegation synthetic key','scopes':['data.query','connectors.read','chat.use','profiles.read'],
                'allowed_profiles':['fast'],'allowed_sources':[allowed],'rpm':120,'validity_days':1})
            check('delegation_scoped_key_created',issued.status_code==201)
            api_key=issued.json()['token']
            def original():
                scope={'type':'http','method':'POST','scheme':'https','path':'/api/v1/connectors/ask','root_path':'','query_string':b'',
                    'headers':[(b'authorization',('Bearer '+api_key).encode())],'app':app,'client':('127.0.0.1',0),'server':('localhost',8443),'state':{}}
                request=Request(scope);request.state.request_id=uuid.uuid4();return request
            request=original();actor=await app.state.auth.authenticate(request)
            ticket=await connector_tickets.issue(request,actor,'fast')
            headers={'Authorization':'Bearer '+config.connector_key,'X-Moara-Execution-Ticket':ticket}
            async with httpx.AsyncClient(transport=transport,base_url=base) as internal:
                check('internal_service_auth_required',(await internal.post('internal/connectors/authorize-query',json={'source_id':allowed})).status_code==401)
                result=await internal.post('internal/connectors/authorize-query',headers=headers,json={'source_id':allowed})
                check('delegated_source_authorized',result.status_code==200)
                denied=await internal.post('internal/connectors/authorize-query',headers=headers,json={'source_id':str(uuid.uuid4())})
                check('delegated_source_scope_enforced',denied.status_code==404)
                wrong=await internal.post('internal/connectors/inference',headers=headers,json={'model':'private','messages':[{'role':'user','content':'Quem é você?'}]})
                check('delegated_model_scope_enforced',wrong.status_code==403)
                canonical=await internal.post('internal/connectors/inference',headers=headers,json={'model':'fast','messages':[{'role':'user','content':'Quem é você?'}]})
                check('delegated_identity_pipeline',canonical.status_code==200 and canonical.json()['moara']['inference_used'] is False)
                revoked=await admin.post('admin/api-keys/'+issued.json()['id']+'/revoke')
                check('delegated_key_revoked',revoked.status_code==200)
                denied=await internal.post('internal/connectors/authorize-query',headers=headers,json={'source_id':allowed})
                check('queued_delegation_revocation_enforced',denied.status_code==401)
                await app.state.db.execute('UPDATE moara.connector_tickets SET expires_at=now()-interval \'1 second\' WHERE token_hash=:hash',{'hash':connector_tickets.digest(ticket)})
                check('expired_delegation_denied',(await internal.post('internal/connectors/authorize-query',headers=headers,json={'source_id':allowed})).status_code==401)
            rows=await app.state.db.execute('SELECT auth_bundle FROM moara.connector_tickets WHERE account_id=CAST(:id AS uuid)',{'id':owner})
            check('delegation_credentials_encrypted',rows and all(api_key not in r['auth_bundle'] and r['auth_bundle'].startswith('gAAAA') for r in rows))
            # Validate the exact production proxy header construction with a mock hub only.
            issued=await admin.post('admin/api-keys',json={'account_id':owner,'name':'Proxy synthetic key','scopes':['connectors.read','chat.use','profiles.read','data.query'],
                'allowed_profiles':['fast'],'allowed_sources':[allowed],'rpm':120,'validity_days':1})
            captured=[]
            def hub(request):
                captured.append(dict(request.headers));return httpx.Response(200,json=[])
            actual=app.state.http
            async with httpx.AsyncClient(transport=httpx.MockTransport(hub)) as mock_hub:
                app.state.http=mock_hub
                try:
                    async with httpx.AsyncClient(transport=transport,base_url=base,headers={'Authorization':'Bearer '+issued.json()['token'],
                        'X-Actor-Id':'key:admin','X-Actor-Admin':'true','X-Actor-Source-Ids':'[]'}) as user:
                        response=await user.get('connectors/sources')
                        check('proxy_real_auth_success',response.status_code==200)
                        check('proxy_discards_forged_actor',captured[-1]['x-actor-id']=='local:'+owner)
                        check('proxy_discards_forged_admin',captured[-1]['x-actor-admin']=='false')
                        check('proxy_overwrites_source_restrictions',json.loads(captured[-1]['x-actor-source-ids'])==[allowed])
                        check('proxy_uses_service_credential',captured[-1]['authorization']=='Bearer '+config.connector_key)
                finally:app.state.http=actual
    return {'passed':True,'checks':checks,'scope':'isolated staging; real PostgreSQL/Redis/auth/ASGI; mock hub transport only; no production inference'}

if __name__=='__main__':
    try:report=asyncio.run(main())
    except Exception as error:report={'passed':False,'checks':checks,'failure_type':type(error).__name__}
    print(json.dumps(report));raise SystemExit(0 if report['passed'] else 1)
