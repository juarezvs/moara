"""Real two-realm LDAPS, native SQLite accounts/sessions and HTTP authorization."""
import asyncio
import hashlib
import hmac
import json
import time
import uuid
from pathlib import Path
import httpx
from open_webui.main import app
from open_webui.models.auths import Auths
from open_webui.models.config import Config
from open_webui.utils.auth import get_password_hash,create_token
from open_webui.utils.mfa import get_auth
from open_webui.utils import moara_directories as directories

checks={}
def check(name,value):
    checks[name]=bool(value)
    if not value:raise AssertionError(name)

async def main():
    fixture=json.loads(Path('/tmp/directory-fixtures.json').read_text());password=fixture['password']
    admin=await Auths.insert_new_auth('admin@qa.invalid',await get_password_hash(password),'Synthetic administrator',role='admin')
    auth=await get_auth(admin.id)
    token=create_token({'id':admin.id,'typ':'session','auth_method':'password','session_stamp':auth.session_stamp})
    transport=httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport,base_url='https://localhost:8443',headers={'Authorization':'Bearer '+token}) as client:
        check('anonymous_admin_denied',(await client.get('/api/v1/moara/directories',headers={'Authorization':''})).status_code==401)
        for row in fixture['directories']:
            response=await client.put('/api/v1/moara/directories/'+row['realm'],json=row)
            check(row['realm']+'_saved',response.status_code==200)
            check(row['realm']+'_password_never_returned',response.json().get('has_password') and 'password_encrypted' not in response.text and password not in response.text)
            response=await client.post('/api/v1/moara/directories/'+row['realm']+'/test')
            check(row['realm']+'_real_ldaps_verified',response.status_code==200 and response.json()['tls_verified'])
        listing=(await client.get('/api/v1/moara/directories/public',headers={'Authorization':''})).json()
        check('public_catalog_has_only_labels',len(listing)==2 and all(set(r)=={'realm','label'} for r in listing))
        tokens={};identifiers={}
        for realm in ('alpha','beta'):
            response=await client.post('/api/v1/auths/ldap',json={'user':realm+'\\alice','password':password},headers={'Authorization':''})
            check(realm+'_native_login',response.status_code==200 and response.json().get('role')=='user' and bool(response.json().get('token')))
            tokens[realm]=response.json()['token'];identifiers[realm]=response.json()['id']
        check('same_username_two_ad_distinct_accounts',identifiers['alpha']!=identifiers['beta'])
        check('native_user_session_valid',(await client.get('/api/v1/auths/',headers={'Authorization':'Bearer '+tokens['alpha']})).status_code==200)
        await Config.upsert({'ldap.enable':False})
        response=await client.post('/api/v1/auths/ldap',json={'user':'alpha\\alice','password':password},headers={'Authorization':''})
        check('global_native_ldap_switch_is_respected',response.status_code==403)
        check('global_disabled_directory_catalog_hidden',(await client.get('/api/v1/moara/directories/public',headers={'Authorization':''})).json()==[])
        await Config.upsert({'ldap.enable':True})
        original=directories.ENABLE_PASSWORD_AUTH;directories.ENABLE_PASSWORD_AUTH=False
        try:
            response=await client.post('/api/v1/auths/ldap',json={'user':'alpha\\alice','password':password},headers={'Authorization':''})
            check('global_native_password_auth_switch_is_respected',response.status_code==403)
        finally:directories.ENABLE_PASSWORD_AUTH=original
        check('ordinary_user_cannot_manage_directories',(await client.get('/api/v1/moara/directories',headers={'Authorization':'Bearer '+tokens['alpha']})).status_code==401)
        response=await client.post('/api/v1/auths/ldap',json={'user':'alpha\\alice','password':''},headers={'Authorization':''})
        check('empty_password_denied',response.status_code==400)
        response=await client.post('/api/v1/auths/ldap',json={'user':'alpha\\alice','password':'wrong'},headers={'Authorization':''})
        check('wrong_password_denied',response.status_code==400)
        response=await client.post('/api/v1/auths/ldap',json={'user':'alpha\\*)(uid=*)','password':password},headers={'Authorization':''})
        check('ldap_filter_injection_denied',response.status_code==400)
        config=fixture['directories'][0].copy();config['ca_pem']=''
        try:await asyncio.to_thread(directories.ldap_operation,{**config,'password_encrypted':directories.cipher().encrypt(password.encode()).decode()})
        except Exception:check('untrusted_certificate_denied',True)
        else:check('untrusted_certificate_denied',False)
        config['host']='moara-ldap-beta';config['ca_pem']=fixture['directories'][0]['ca_pem']
        try:await asyncio.to_thread(directories.ldap_operation,{**config,'password_encrypted':directories.cipher().encrypt(password.encode()).decode()})
        except Exception:check('other_realm_certificate_denied',True)
        else:check('other_realm_certificate_denied',False)
        config=fixture['directories'][0].copy();config['required_groups']=['cn=not-authorized,'+config['search_base']]
        check('group_restriction_saved',(await client.put('/api/v1/moara/directories/alpha',json=config)).status_code==200)
        response=await client.post('/api/v1/auths/ldap',json={'user':'alpha\\alice','password':password},headers={'Authorization':''})
        check('unapproved_group_denied',response.status_code==400)
        check('restricted_directory_revokes_old_session',(await client.get('/api/v1/auths/',headers={'Authorization':'Bearer '+tokens['alpha']})).status_code==401)
        check('other_directory_session_independent',(await client.get('/api/v1/auths/',headers={'Authorization':'Bearer '+tokens['beta']})).status_code==200)
        raw=directories.STORE.read_bytes()
        check('bind_password_encrypted_at_rest',password.encode() not in raw)
        config=fixture['directories'][1].copy();config['enabled']=False;config.pop('bind_password')
        response=await client.put('/api/v1/moara/directories/beta',json=config)
        check('disable_keeps_stored_password',response.status_code==200 and response.json()['has_password'])
        check('disable_revokes_native_session',(await client.get('/api/v1/auths/',headers={'Authorization':'Bearer '+tokens['beta']})).status_code==401)
        response=await client.post('/api/v1/auths/ldap',json={'user':'beta\\alice','password':password},headers={'Authorization':''})
        check('disabled_directory_login_denied',response.status_code==400)
        config['enabled']=True;config['new_user_role']='admin'
        check('ad_cannot_auto_grant_admin',(await client.put('/api/v1/moara/directories/beta',json=config)).status_code==422)
        response=await client.put('/api/v1/moara/directories/beta',json=fixture['directories'][1],headers={'Origin':'https://other.invalid'})
        check('foreign_origin_admin_write_denied',response.status_code==403)
        org={'sigla':'QA','name':'Synthetic organization','enabled':True}
        response=await client.put('/api/v1/moara/organizations/QA',json=org)
        check('organization_registry_create',response.status_code==200)
        config=fixture['directories'][1].copy();config['organization']='QA'
        check('directory_linked_to_organization',(await client.put('/api/v1/moara/directories/beta',json=config)).status_code==200)
        response=await client.post('/api/v1/auths/ldap',json={'user':'beta\\alice','password':password},headers={'Authorization':''})
        check('organization_login_enabled',response.status_code==200)
        unit_token=response.json()['token'];unit_id=response.json()['id']
        response=await client.get('/api/v1/moara/organizations',headers={'Authorization':'Bearer '+unit_token})
        check('ordinary_member_cannot_manage_organizations',response.status_code==401)
        response=await client.get('/api/v1/moara/internal/identity/'+unit_id,headers={'Authorization':''})
        check('institutional_membership_requires_signed_request',response.status_code==401)
        def signed():
            stamp=str(int(time.time()));key=Path('/run/secrets/moara_forward_jwt_secret').read_bytes().strip()
            return {'Authorization':'','X-Moara-Timestamp':stamp,'X-Moara-Signature':hmac.new(key,(stamp+':'+unit_id).encode(),hashlib.sha256).hexdigest()}
        response=await client.get('/api/v1/moara/internal/identity/'+unit_id,headers=signed())
        check('server_side_membership_verified',response.status_code==200 and response.json().get('organization')=='QA' and response.json().get('enabled') is True and response.json().get('institutional_verified') is True)
        org['enabled']=False;await client.put('/api/v1/moara/organizations/QA',json=org)
        check('organization_hidden_from_login',all(r['realm']!='beta' for r in (await client.get('/api/v1/moara/directories/public')).json()))
        response=await client.post('/api/v1/auths/ldap',json={'user':'beta\\alice','password':password},headers={'Authorization':''})
        check('inactive_organization_denies_login',response.status_code==400)
        check('inactive_organization_revokes_native_session',(await client.get('/api/v1/auths/',headers={'Authorization':'Bearer '+unit_token})).status_code==401)
        response=await client.get('/api/v1/moara/internal/identity/'+unit_id,headers=signed())
        check('inactive_membership_blocks_gateway_keys',response.status_code==200 and response.json()['enabled'] is False)
        org['enabled']=True;await client.put('/api/v1/moara/organizations/QA',json=org)
        check('reactivation_does_not_revive_old_session',(await client.get('/api/v1/auths/',headers={'Authorization':'Bearer '+unit_token})).status_code==401)
        direct={k:v for k,v in fixture['directories'][0].items() if k not in ('bind_dn','bind_password')}
        direct.update(realm='directqa',organization='QA',authentication_mode='user_bind',netbios_domain='SYNTHETIC')
        response=await client.put('/api/v1/moara/directories/directqa',json=direct)
        check('direct_bind_requires_no_privileged_password',response.status_code==200 and not response.json()['has_password'])
        response=await client.post('/api/v1/moara/directories/directqa/test')
        check('direct_bind_tls_probe_without_service_account',response.status_code==200 and response.json()['tls_verified'])
    print('DIRECTORY_REPORT='+json.dumps({'passed':all(checks.values()),'checks':checks,'scope':'Two synthetic OpenLDAP servers over verified LDAPS, real native HTTP/auth/SQLite; no corporate credentials'}))

asyncio.run(main())
