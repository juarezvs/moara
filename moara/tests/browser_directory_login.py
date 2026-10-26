"""Native LDAP form, two isolated directories; synthetic frontend is HTTP only.

The real production UI has a separate HTTPS browser suite. These LDAP backends
use verified TLS. No synthetic directory is added to production configuration.
"""
import json
import os
import sys
from playwright.sync_api import sync_playwright,expect

fixture=json.load(sys.stdin);checks={};identities=[]
with sync_playwright() as p:
    browser=p.chromium.launch(chromium_sandbox=True,args=['--host-resolver-rules=MAP moara-directory-test '+fixture['ip']],env={**os.environ,'HOME':'/tmp/moara-browser-home'})
    for realm in ('alpha','beta'):
        context=browser.new_context();page=context.new_page()
        page.goto('http://moara-directory-test:8080/auth');page.locator('#moara-directory-choice').wait_for(timeout=30000)
        checks[realm+'_directory_selector']=page.locator('#moara-directory-choice option').count()==2
        page.locator('#moara-directory-choice').select_option(realm)
        page.locator('#username').fill('alice');page.locator('#password').fill(fixture['password'])
        with page.expect_response(lambda r:r.url.endswith('/api/v1/auths/ldap'),timeout=30000) as login:
            page.locator('form button[type=submit]').click()
        response=login.value;result=response.json()
        checks[realm+'_prefix_applied']=response.request.post_data_json.get('user')==realm+'\\alice'
        checks[realm+'_native_browser_login']=response.status==200 and bool(result.get('token')) and result.get('role')=='user'
        if not checks[realm+'_native_browser_login']:raise AssertionError(realm+'_native_browser_login')
        identities.append(result['id']);context.close()
    checks['two_directories_distinct_browser_identities']=len(set(identities))==2
    browser.close()
print(json.dumps({'passed':all(checks.values()),'checks':checks,'scope':'Synthetic native HTTP frontend inside isolated containers; both directory binds use verified LDAPS. Production frontend TLS tested separately.'}))
