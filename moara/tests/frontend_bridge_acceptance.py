"""Real isolated Core/PG/Redis; only upstream service authentication is mocked."""
import asyncio
import hashlib
import hmac
import json
import time
import uuid
import httpx
import jwt
from moara.gateway.api import create_app
from moara.gateway.settings import Settings

async def main():
    checks={};settings=Settings.load();app=create_app(settings)
    def check(name,value):
        checks[name]=bool(value)
        if not value:raise AssertionError(name)
    async with app.router.lifespan_context(app):
        original=app.state.auth.http
        original_transport=app.state.http
        native_id=str(uuid.uuid4());native={'id':native_id,'name':'Synthetic native administrator','email':'native-admin@qa.invalid','role':'admin'}
        native_users=[native];access={'allowed':True};unit={'organization':None,'enabled':True,'available':True}
        def upstream(request):
            if request.url.path.startswith('/api/v1/moara/internal/identity/'):
                identifier=request.url.path.rsplit('/',1)[-1];stamp=request.headers.get('x-moara-timestamp','')
                signature=hmac.new(settings.forward_key.encode(),(stamp+':'+identifier).encode(),hashlib.sha256).hexdigest()
                if request.headers.get('x-moara-signature')!=signature:return httpx.Response(401)
                if not unit['available']:return httpx.Response(503)
                return httpx.Response(200,json={k:unit[k] for k in ('organization','enabled')})
            if request.url.path=='/v1/auth/identity':return httpx.Response(200,json={'id':'webui','scopes':['chat']})
            if request.url.path=='/api/v1/auths/':return httpx.Response(200,json=native)
            if request.url.path=='/api/v1/users/':return httpx.Response(200,json={'users':native_users,'total':len(native_users)}) if access['allowed'] else httpx.Response(403)
            return httpx.Response(401)
        async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as authentication:
            app.state.auth.http=authentication
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://localhost:8443/moara/v1/',headers={'Authorization':'Bearer synthetic-webui-reserved-key'}) as client:
                    response=await client.post('chat/completions',json={'model':'auto','messages':[{'role':'user','content':'Quem é você?'}]})
                    check('shared_frontend_key_cannot_infer_without_signed_user',response.status_code==401)
                    claims={'sub':str(uuid.uuid4()),'name':'Synthetic frontend user','email':'frontend@qa.invalid','role':'user','iss':'open-webui','iat':int(time.time()),'exp':int(time.time())+60}
                    def signed(value):return jwt.encode(value,settings.forward_key,algorithm='HS256')
                    client.headers['X-OpenWebUI-User-Jwt']=signed(claims)
                    response=await client.get('models')
                    check('automatic_profile_visible_to_authorized_frontend_user',response.status_code==200 and any(r['id']=='auto' for r in response.json()['data']))
                    response=await client.post('chat/completions',json={'model':'auto','stream':True,'messages':[{'role':'user','content':'Quem é você?'}]})
                    check('signed_frontend_user_reaches_identity_and_routing',response.status_code==200 and '[DONE]' in response.text and 'Moara' in response.text)
                    response=await client.post('chat/completions',json={'model':'coding','messages':[{'role':'user','content':'Quem é você?'}]})
                    check('frontend_user_cannot_use_private_admin_profile',response.status_code==403)
                    client.headers['X-OpenWebUI-User-Jwt']=signed({**claims,'exp':claims['iat']+300})
                    check('overlong_forwarding_lifetime_denied',(await client.get('models')).status_code==401)
                    client.headers['X-OpenWebUI-User-Jwt']=signed({**claims,'iss':'untrusted'})
                    check('wrong_forwarding_issuer_denied',(await client.get('models')).status_code==401)
                    client.headers['X-OpenWebUI-User-Jwt']=jwt.encode(claims,'different-synthetic-key-with-enough-length',algorithm='HS256')
                    check('forged_forwarded_user_denied',(await client.get('models')).status_code==401)
                    client.headers['X-OpenWebUI-User-Jwt']=signed({**claims,'role':'pending'})
                    check('pending_native_user_denied',(await client.get('models')).status_code==403)
                    client.headers['X-OpenWebUI-User-Jwt']=signed(claims)
                    check('shared_frontend_cannot_synchronize_users',(await client.post('https://localhost:8443/moara/api/v1/admin/accounts/sync-institutional',json={})).status_code==403)
                    group=str(uuid.uuid5(uuid.NAMESPACE_URL,'moara:organization:QA'))
                    unit['organization']='QA'
                    response=await client.get('models')
                    check('verified_ad_membership_grants_unit_chat_profile',response.status_code==200 and any(m['id']=='coding' for m in response.json()['data']))
                    membership=await app.state.db.execute('SELECT group_id FROM moara.group_members WHERE account_id=CAST(:id AS uuid)',{'id':claims['sub']})
                    check('new_organization_needs_no_manual_database_setup',any(str(m['group_id'])==group for m in membership))
                    admin_headers={'Authorization':'Bearer synthetic.native.session','X-OpenWebUI-User-Jwt':''}
                    response=await client.post('https://localhost:8443/moara/api/v1/admin/api-keys',headers=admin_headers,json={
                        'name':'Synthetic unit scoped key','account_id':claims['sub'],'scopes':['chat.use','profiles.read','identity.read'],
                        'allowed_profiles':['coding'],'allowed_sources':[],'rpm':30,'validity_days':1})
                    check('unit_integration_key_created',response.status_code==201)
                    key=response.json();key_headers={'Authorization':'Bearer '+key['token'],'X-OpenWebUI-User-Jwt':''}
                    check('active_unit_key_works',(await client.get('models',headers=key_headers)).status_code==200)
                    unit['enabled']=False
                    check('inactive_unit_blocks_signed_frontend',(await client.get('models')).status_code==403)
                    check('inactive_unit_blocks_existing_api_key',(await client.get('models',headers=key_headers)).status_code==403)
                    unit['enabled']=True;unit['available']=False
                    check('unit_status_outage_fails_closed',(await client.get('models',headers=key_headers)).status_code==503)
                    unit['available']=True
                    await client.post('https://localhost:8443/moara/api/v1/admin/api-keys/'+key['id']+'/revoke',headers=admin_headers,json={})
                    await app.state.db.execute('UPDATE moara.accounts SET active=false WHERE id=CAST(:id AS uuid)',{'id':claims['sub']})
                    check('disabled_core_user_denied_despite_valid_frontend_jwt',(await client.get('models')).status_code==403)
                    # Native UI account sync retains local suspension and roles.
                    native_users.append({**claims,'id':claims['sub'],'role':'admin'})
                    absent=await app.state.auth.upsert_legacy({'id':str(uuid.uuid4()),'role':'user','email':'removed@qa.invalid','name':'Removed synthetic native user'})
                    client.headers['Authorization']='Bearer synthetic.native.session'
                    client.headers.pop('X-OpenWebUI-User-Jwt',None);app.state.http=authentication
                    response=await client.post('https://localhost:8443/moara/api/v1/admin/accounts/sync-institutional',json={})
                    check('native_account_sync_requires_verified_full_inventory',response.status_code==200 and response.json()['kept_disabled']==1 and response.json()['suspended']>=1)
                    absent_state=await app.state.db.execute('SELECT active FROM moara.accounts WHERE id=CAST(:id AS uuid)',{'id':str(absent['id'])},one=True)
                    check('missing_native_account_is_suspended',absent_state['active'] is False)
                    row=await app.state.db.execute('SELECT active FROM moara.accounts WHERE id=CAST(:id AS uuid)',{'id':claims['sub']},one=True)
                    check('native_sync_does_not_reenable_suspended_core_account',row['active'] is False)
                    role=await app.state.db.execute('SELECT role_id FROM moara.account_roles WHERE account_id=CAST(:id AS uuid)',{'id':claims['sub']})
                    check('native_sync_does_not_escalate_existing_core_roles',[r['role_id'] for r in role]==['user'])
                    access['allowed']=False
                    check('native_non_admin_cannot_sync_accounts',(await client.post('https://localhost:8443/moara/api/v1/admin/accounts/sync-institutional',json={})).status_code==403)
            finally:app.state.auth.http=original;app.state.http=original_transport
    print(json.dumps({'passed':all(checks.values()),'checks':checks,'scope':'Isolated actual Core/auth/PG/Redis; upstream reserved-key authentication deliberately mocked'}))

asyncio.run(main())
