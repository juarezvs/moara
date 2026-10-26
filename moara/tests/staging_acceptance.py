"""Run inside the isolated staging API: real HTTP, PostgreSQL, Redis and crypto.

Fixtures below are exclusively synthetic. No production model inference or
institutional account is changed. Never print returned credentials.
"""
import asyncio
import json
import uuid
import os
from pathlib import Path
from datetime import datetime,timezone
import httpx
from moara.gateway.database import Database
from moara.gateway.settings import Settings

BASE='http://127.0.0.1:8075/moara/api/v1'
ORIGIN='https://localhost:8443'
checks=[]
def check(name,value):
    checks.append({'name':name,'passed':bool(value)})
    if not value:raise AssertionError(name)

class Client:
    def __init__(self):self.http=httpx.Client(base_url=BASE+'/',headers={'Origin':ORIGIN},timeout=30);self.csrf=''
    def request(self,method,path,body=None):
        headers={'X-Moara-CSRF':self.csrf} if self.csrf else {}
        return self.http.request(method,path,json=body,headers=headers)
    def login(self,email,password):
        response=self.request('POST','auth/login',{'email':email,'password':password})
        check('login_'+email,response.status_code==200)
        token=response.cookies.get('__Secure-moara_session')
        check('secure_cookie',all(v in response.headers.get('set-cookie','').lower() for v in ['secure','httponly','samesite=strict','path=/moara']))
        # Local container HTTP does not send secure cookies automatically.
        # Public browser acceptance separately verifies the real HTTPS transport.
        self.http.headers['Cookie']='__Secure-moara_session='+token
        self.csrf=response.json()['csrf_token']

async def seed():
    from moara.gateway import bootstrap
    from moara.gateway.auth import Auth
    db=Database(Settings.load());model=str(uuid.uuid5(bootstrap.NAMESPACE,'fixture:test-only'))
    catalog={'accounts':[],'groups':[],'group_members':[],'models':[{'id':'fast','name':'Synthetic staging fixture','is_active':1}],
        'grants':[{'resource_id':'fast','permission':'read','principal_type':'anyone','principal_id':'*'}],
        'physical_models':[{'alias':'fast','provider':'fixture','tag':'test-only','details':{'context_length':8192},
            'declared_capabilities':['completion'],'size_bytes':0,'digest':'synthetic-staging-fixture'}]}
    path=Path('/tmp/synthetic-bootstrap-catalog.json');path.write_text(json.dumps(catalog))
    os.environ['MOARA_BOOTSTRAP_CATALOG']=str(path)
    async with httpx.AsyncClient() as http:
        auth=Auth(Settings.load(),db,http)
        try:await bootstrap.seed(db,auth)
        finally:await auth.close()
    path.unlink();os.environ.pop('MOARA_BOOTSTRAP_CATALOG',None)
    row=await db.execute("SELECT enabled FROM moara.profiles WHERE id='fast'",one=True)
    check('legacy_integer_boolean_import',row['enabled'] is True)
    for name,public in [('private',False)]:
        await db.execute('''INSERT INTO moara.profiles(id,name,public,category,settings) VALUES(:id,:id,:public,'general',CAST(:settings AS jsonb))''',
            {'id':name,'public':public,'settings':json.dumps({'threads':12,'context_length':8192,'max_tokens':256,'temperature':0.2,'timeout':60})})
        await db.execute('INSERT INTO moara.profile_models(profile_id,model_id) VALUES(:id,CAST(:model AS uuid))',{'id':name,'model':model})
    await db.dispose()

async def encrypted_at_rest(identifier,text):
    db=Database(Settings.load());row=await db.execute('SELECT content FROM moara.messages WHERE chat_id=CAST(:id AS uuid) LIMIT 1',{'id':identifier},one=True)
    check('history_encrypted_at_rest',row and text not in row['content'] and row['content'].startswith('gAAAA'))
    await db.dispose()

def main():
    asyncio.run(seed());admin=Client();user=Client();other=Client()
    check('unauthenticated_denied',user.request('GET','admin/accounts').status_code==401)
    check('public_identity_available',user.request('GET','identity/public').status_code==200)
    admin.login('admin@staging.invalid',Path('/run/secrets/admin_password').read_text())
    user_id=None
    for client,email in [(user,'user@staging.invalid'),(other,'other@staging.invalid')]:
        created=admin.request('POST','admin/accounts',{'name':'Synthetic acceptance user','email':email,'roles':['user']})
        check('account_create_'+email,created.status_code==201)
        if client is user:user_id=created.json()['id']
        client.login(email,created.json()['temporary_password'])
        check('initial_password_gate',client.request('GET','profiles').status_code==403)
        new_password=uuid.uuid4().hex+uuid.uuid4().hex
        check('initial_password_change',client.request('PUT','auth/password',{'password':new_password}).status_code==200)
        check('incorrect_current_password_denied',client.request('PUT','auth/password',{'password':uuid.uuid4().hex,'current_password':'incorrect'}).status_code==401)
    check('role_header_forgery_denied',user.http.get('admin/accounts',headers={'X-Actor-Admin':'true','X-Role':'administrator'}).status_code==403)
    check('non_admin_catalog_denied',user.request('GET','models').status_code==403)
    check('profile_acl_list', [p['id'] for p in user.request('GET','profiles').json()]==['fast'])
    check('manual_private_profile_denied',user.request('POST','chat/completions',{'model':'private','messages':[{'role':'user','content':'Quem é você?'}]}).status_code==403)
    canonical=user.request('POST','chat/completions',{'model':'fast','messages':[{'role':'user','content':'Quem é você?'}]})
    check('canonical_chat_without_inference',canonical.status_code==200 and canonical.json()['moara']['inference_used'] is False and canonical.json()['usage']['total_tokens']==0)
    stream=user.request('POST','chat/completions',{'model':'fast','stream':True,'messages':[{'role':'user','content':'Quem é você?'}]})
    check('canonical_sse',stream.status_code==200 and 'data: [DONE]' in stream.text and 'Moara' in stream.text)
    # A forced tool contract cannot be answered with an identity FAQ instead.
    forced=user.request('POST','chat/completions',{'model':'fast','tool_choice':'required','tools':[{'type':'function','function':{'name':'read','parameters':{'type':'object','properties':{}}}}],
        'messages':[{'role':'user','content':'Quem é você?'}]})
    check('tool_capability_enforced',forced.status_code==409)
    check('csrf_enforced',user.http.put('auth/preferences',json={'theme':'dark'}).status_code==403)
    check('origin_enforced',user.http.put('auth/preferences',json={'theme':'dark'},headers={'Origin':'https://evil.invalid','X-Moara-CSRF':user.csrf}).status_code==403)
    check('theme_saved',user.request('PUT','auth/preferences',{'theme':'dark'}).status_code==200 and user.request('GET','auth/me').json()['preferences']['theme']=='dark')
    chat=user.request('POST','chats',{'title':'Synthetic history'}).json();text='Only synthetic content '+uuid.uuid4().hex
    body={'title':'Synthetic history','profile_id':'fast','expected_updated_at':chat['updated_at'],'messages':[{'role':'user','content':text}]}
    check('history_saved',user.request('PUT','chats/'+chat['id'],body).status_code==200)
    check('history_revision_conflict',user.request('PUT','chats/'+chat['id'],body).status_code==409)
    check('history_owner_read',user.request('GET','chats/'+chat['id']).json()['messages'][0]['content']==text)
    check('history_idor_read_denied',other.request('GET','chats/'+chat['id']).status_code==404)
    check('history_idor_delete_denied',other.request('DELETE','chats/'+chat['id']).status_code==404)
    asyncio.run(encrypted_at_rest(chat['id'],text))
    identity=admin.request('GET','identity').json();original_id=identity['publication']['id'];original_hash=identity['sha256']
    document={k:v for k,v in identity.items() if k not in ('publication','sha256')};document['version']='1.0.1'
    draft=admin.request('POST','identity/drafts',{'body':document}).json()
    document['version']='1.0.2';edited=admin.request('PUT','identity/drafts/'+draft['id'],{'body':document,'expected_sha256':draft['sha256']})
    check('draft_revision_created',edited.status_code==200 and edited.json()['id']!=draft['id'])
    check('draft_history_preserved',admin.request('GET','identity/versions/'+draft['id']).json()['body']['version']=='1.0.1')
    check('old_draft_immutable',admin.request('PUT','identity/drafts/'+draft['id'],{'body':document,'expected_sha256':draft['sha256']}).status_code==409)
    newest=edited.json()
    check('identity_publish_rbac',user.request('POST','identity/drafts/'+newest['id']+'/publish',{'expected_active_id':original_id,'expected_sha256':newest['sha256']}).status_code==403)
    published=admin.request('POST','identity/drafts/'+newest['id']+'/publish',{'expected_active_id':original_id,'expected_sha256':newest['sha256']})
    check('identity_published',published.status_code==200 and admin.request('GET','identity').json()['version']=='1.0.2')
    check('published_immutable',admin.request('PUT','identity/drafts/'+newest['id'],{'body':document,'expected_sha256':newest['sha256']}).status_code==409)
    restored=admin.request('POST','identity/versions/'+original_id+'/restore',{'expected_active_id':newest['id'],'expected_sha256':original_hash})
    check('identity_restore_provenance',restored.status_code==200 and restored.json()['id']!=original_id and restored.json()['restored_from']==original_id)
    key=admin.request('POST','admin/api-keys',{'account_id':user_id,'name':'Synthetic test key','scopes':['chat.use','profiles.read'],
        'allowed_profiles':['fast'],'rpm':60,'validity_days':1})
    check('key_created',key.status_code==201)
    token=key.json()['token'];headers={'Authorization':'Bearer '+token}
    check('key_valid',httpx.get(BASE+'/profiles',headers=headers).status_code==200)
    check('key_no_admin_privileges',httpx.get(BASE+'/admin/accounts',headers=headers).status_code==403)
    check('keys_never_return_hashes',all('token' not in r and 'token_hash' not in r for r in admin.request('GET','admin/api-keys').json()))
    check('key_revoke',admin.request('POST','admin/api-keys/'+key.json()['id']+'/revoke').status_code==200)
    check('revoked_key_denied',httpx.get(BASE+'/profiles',headers=headers).status_code==401)
    check('last_administrator_protected',admin.request('PUT','admin/accounts/'+admin.request('GET','auth/me').json()['id'],{'active':False,'roles':['user']}).status_code==409)
    check('account_disable',admin.request('PUT','admin/accounts/'+user_id,{'active':False,'roles':['user']}).status_code==200)
    check('disabled_session_denied',user.request('GET','auth/me').status_code==401)
    check('audit_metadata_only',all(not any(k in r for k in ('prompt','password','token','content')) for r in admin.request('GET','audit').json()))
    installation={'catalog_id':'gemma4-12b','idempotency_key':'synthetic-install-test'}
    queued=admin.request('POST','admin/model-installations',installation)
    check('durable_job_created',queued.status_code==202 and queued.json()['status']=='queued')
    repeat=admin.request('POST','admin/model-installations',installation)
    check('durable_job_idempotency',repeat.status_code==202 and repeat.json()['id']==queued.json()['id'] and repeat.json()['reused'])
    conflict=admin.request('POST','admin/model-installations',{**installation,'catalog_id':'qwen25-coder-7b'})
    check('durable_job_payload_conflict',conflict.status_code==409)
    check('unapproved_install_denied',admin.request('POST','admin/model-installations',{**installation,'catalog_id':'untrusted-model'}).status_code==422)
    check('job_other_owner_denied',other.request('GET','jobs/'+queued.json()['id']).status_code==404)
    check('job_cancelled',admin.request('POST','jobs/'+queued.json()['id']+'/cancel').status_code==200)
    check('job_cancel_persisted',admin.request('GET','jobs/'+queued.json()['id']).json()['status']=='cancelled')
    return {'passed':True,'scope':'isolated synthetic staging; real HTTP/PostgreSQL/Redis; no production inference','checks':checks,'timestamp':datetime.now(timezone.utc).isoformat()}

if __name__=='__main__':
    try:report=main()
    except Exception as error:
        report={'passed':False,'checks':checks,'failure_type':type(error).__name__}
    print(json.dumps(report,ensure_ascii=False));raise SystemExit(0 if report['passed'] else 1)
