"""Disposable TLS LDAP fixtures; no production directory credentials or ports."""
import json
import os
import secrets
import subprocess
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
PRIVATE=ROOT/'secrets/moara-directory-qa'
NETWORK='moara-directory-qa'
IMAGE='osixia/openldap@sha256:18742e9c449c9c1afe129d3f2f3ee15fb34cc43e5f940a20f3399728f41d7c28'

def run(args,**kwargs):
    result=subprocess.run(args,capture_output=True,**kwargs)
    if result.returncode:raise RuntimeError('Directory fixture command failed: '+str(args[:3]))
    return result.stdout

def main():
    PRIVATE.mkdir(mode=0o700,exist_ok=True)
    password=secrets.token_hex(24)
    (PRIVATE/'webui_secret').write_text(secrets.token_hex(32));os.chmod(PRIVATE/'webui_secret',0o644)
    run(['docker','network','create','--internal','--label','moara.test=directory',NETWORK])
    fixtures=[]
    for realm in ('alpha','beta'):
        name='moara-ldap-'+realm;domain=realm+'.invalid';base='dc='+realm+',dc=invalid'
        certs=PRIVATE/(realm+'-'+secrets.token_hex(4));certs.mkdir()
        run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','2','-subj','/CN=Moara QA '+realm,
            '-keyout',str(certs/'ca.key'),'-out',str(certs/'ca.crt')])
        run(['openssl','req','-newkey','rsa:2048','-nodes','-subj','/CN='+name,'-keyout',str(certs/'server.key'),'-out',str(certs/'server.csr')])
        (certs/'extensions').write_text('subjectAltName=DNS:'+name+'\nextendedKeyUsage=serverAuth\n')
        run(['openssl','x509','-req','-in',str(certs/'server.csr'),'-CA',str(certs/'ca.crt'),'-CAkey',str(certs/'ca.key'),
            '-CAcreateserial','-days','2','-extfile',str(certs/'extensions'),'-out',str(certs/'server.crt')])
        run(['openssl','genpkey','-genparam','-algorithm','DH','-pkeyopt','group:ffdhe2048','-out',str(certs/'dhparam.pem')])
        run(['docker','run','-d','--name',name,'--hostname',name,'--label','moara.test=directory','--network',NETWORK,
            '--memory','512m','--cpus','1','--pids-limit','128','-e','LDAP_ORGANISATION=Moara synthetic QA',
            '-e','LDAP_DOMAIN='+domain,'-e','LDAP_ADMIN_PASSWORD='+password,'-e','LDAP_CONFIG_PASSWORD='+password,
            '-e','LDAP_TLS_VERIFY_CLIENT=never','-e','LDAP_TLS_CRT_FILENAME=server.crt',
            '-e','LDAP_TLS_KEY_FILENAME=server.key','-e','LDAP_TLS_CA_CRT_FILENAME=ca.crt',
            '--mount',f'type=bind,source={certs},target=/container/service/slapd/assets/certs',IMAGE])
        for attempt in range(75):
            result=subprocess.run(['docker','exec',name,'ldapwhoami','-x','-H','ldap://localhost','-D','cn=admin,'+base,'-w',password],capture_output=True)
            if not result.returncode:break
            time.sleep(1)
        else:raise RuntimeError('Synthetic LDAP readiness timed out')
        ldif=f'dn: uid=alice,{base}\nobjectClass: inetOrgPerson\ncn: Synthetic Alice {realm}\nsn: QA\nuid: alice\nmail: alice@{domain}\nuserPassword: {password}\n\n'
        for attempt in range(30):
            result=subprocess.run(['docker','exec',name,'cat','/container/service/slapd/assets/certs/ca.crt'],capture_output=True)
            if result.returncode==0:ca=result.stdout.decode();break
            time.sleep(1)
        else:raise RuntimeError('Synthetic TLS certificate not ready')
        for attempt in range(90):
            result=subprocess.run(['docker','exec','-e','LDAPTLS_CACERT=/container/service/slapd/assets/certs/ca.crt',name,
                'ldapwhoami','-x','-H','ldaps://'+name,'-D','cn=admin,'+base,'-w',password],capture_output=True)
            if result.returncode==0:break
            time.sleep(1)
        else:raise RuntimeError('Verified synthetic LDAPS readiness timed out')
        run(['docker','exec','-i',name,'ldapadd','-x','-H','ldap://localhost','-D','cn=admin,'+base,'-w',password],input=ldif.encode())
        fixtures.append({'realm':realm,'label':'Synthetic '+realm,'host':name,'port':636,'search_base':base,
            'bind_dn':'cn=admin,'+base,'bind_password':password,'ca_pem':ca,'username_attribute':'uid','identity_attribute':'entryUUID',
            'required_groups':[],'new_user_role':'user','enabled':True})
    run(['docker','run','-d','--name','moara-directory-test','--label','moara.test=directory','--network',NETWORK,
        '--memory','2g','--cpus','2','--pids-limit','256','--security-opt','no-new-privileges:true',
        '--mount',f'type=bind,source={PRIVATE}/webui_secret,target=/run/secrets/webui_secret,readonly',
        '--mount',f'type=bind,source={PRIVATE}/webui_secret,target=/run/secrets/moara_forward_jwt_secret,readonly',
        '--tmpfs','/app/backend/data:rw,size=256m','--tmpfs','/tmp:rw,size=256m',
        '-e','WEBUI_SECRET_KEY='+secrets.token_hex(32),'-e','OFFLINE_MODE=True','-e','GLOBAL_LOG_LEVEL=ERROR',
        '-e','ENABLE_PERSISTENT_CONFIG=False','--entrypoint','sleep','ai-webui:moara-integrated-v1','infinity'])
    run(['docker','exec','-i','moara-directory-test','sh','-c','cat > /tmp/directory-fixtures.json'],input=json.dumps({'directories':fixtures,'password':password}).encode())
    run(['docker','exec','-i','moara-directory-test','sh','-c','cat > /tmp/directory-acceptance.py'],input=(ROOT/'moara/tests/directory_acceptance.py').read_bytes())
    result=subprocess.run(['docker','exec','-e','PYTHONPATH=/app/backend','moara-directory-test','python','/tmp/directory-acceptance.py'],capture_output=True,text=True,timeout=180)
    if result.returncode:
        diagnostic=result.stderr.replace(password,'[REDACTED]')
        (PRIVATE/'error.log').write_text(diagnostic);os.chmod(PRIVATE/'error.log',0o600)
        print('DIRECTORY_ACCEPTANCE_FAILED; private diagnostic retained')
        raise SystemExit(1)
    lines=[l for l in result.stdout.splitlines() if l.startswith('DIRECTORY_REPORT=')]
    if len(lines)!=1:raise RuntimeError('Missing directory acceptance report')
    report=json.loads(lines[0].split('=',1)[1]);(ROOT/'docs/runtime/moara-directory-acceptance.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))

if __name__=='__main__':main()
