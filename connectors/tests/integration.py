"""Real connector tests using only explicitly labeled synthetic databases.

Run in the hub with fixture credentials on stdin. Reports never include values,
passwords, SQL row contents, tokens, or plaintext questions.
"""
import json
import sqlite3
import sys
import uuid
from pathlib import Path
import httpx

fixture=json.load(sys.stdin);key=Path('/run/secrets/connector_hub_key').read_text().strip()
OWNER='local:00000000-0000-0000-0000-000000000111'
OTHER='local:00000000-0000-0000-0000-000000000222'
client=httpx.Client(base_url='http://127.0.0.1:8070/v1/',headers={'Authorization':'Bearer '+key,'X-Actor-Id':OWNER,'X-Actor-Admin':'true'},timeout=45)
checks=[];failures=[];sources=fixture.get('sources',{})
def check(name,condition):
    checks.append({'name':name,'passed':bool(condition)})
    if not condition:raise AssertionError(name)
def call(method,path,body=None,headers=None):
    response=client.request(method,path,json=body,headers=headers)
    if response.status_code>=400:raise RuntimeError(str(response.status_code)+' '+str(response.json().get('detail','request_failed'))[:200])
    return response.json()
def user_headers(owner=OWNER,restriction=None):
    headers={'Authorization':'Bearer '+key,'X-Actor-Id':owner,'X-Actor-Admin':'false'}
    if restriction is not None:headers['X-Actor-Source-Ids']=json.dumps(restriction)
    return headers

specs=[('pg-ponto','postgres','cc-fixture-pg',5432,'cc_ponto','app.ponto'),
    ('pg-cadastro','postgres','cc-fixture-pg',5432,'cc_cadastro','app.people'),
    ('mysql','mysql','cc-fixture-mysql',3306,'rh','rh.employees'),
    ('mariadb','mysql','cc-fixture-mariadb',3306,'rh','rh.employees'),
    ('oracle','oracle','cc-fixture-oracle',1521,'FREEPDB1','CC_DATA.EMPLOYEES'),
    ('mssql','mssql','cc-fixture-mssql',1433,'cc_hr','app.employees'),
    ('mongodb','mongodb','cc-fixture-mongodb',27017,'cc_docs','employees'),
    ('sqlite','sqlite','',0,'synthetic-snapshot','main.employees'),
    ('rest','rest','cc-fixture-rest',8080,'','/employees')]

for label,kind,host,port,database,obj in specs:
    try:
        connection={'host':host,'port':port,'database':database,'username':'CC_READER' if kind=='oracle' else 'cc_reader','tls':False,'timeout':10}
        credential={'password':fixture['reader_password']}
        if kind=='rest':
            connection.update(base_url='http://cc-fixture-rest:8080',endpoints=['/employees'],readonly_endpoints_attested=True)
            credential={'token':fixture['token'],'readonly_token_attested':'true'}
        if kind=='sqlite':
            path=Path('/tmp/connector-acceptance-snapshot.db')
            path.unlink(missing_ok=True);db=sqlite3.connect(path)
            db.execute('CREATE TABLE employees(id integer PRIMARY KEY,nome text,saldo_minutos integer,email text)')
            db.executemany('INSERT INTO employees VALUES(?,?,?,?)',[(1,'Synthetic A',120,'a@example.invalid'),(2,'Synthetic B',60,'b@example.invalid'),(3,'Synthetic C',0,'c@example.invalid')]);db.commit();db.close()
            response=client.post('sqlite/import',content=path.read_bytes(),headers={'Content-Type':'application/octet-stream'})
            check('sqlite_snapshot_import',response.status_code==200);connection['sqlite_id']=response.json()['sqlite_id'];credential=None;path.unlink()
        body={'name':'_reconstruction_fixture_'+label,'description':'Synthetic isolated acceptance fixture; never a corporate data source.',
            'kind':kind,'connection':connection,'credential':credential,'policy':{'owners':[OWNER],'max_rows':2,'timeout':10,'allow_sensitive':False,'objects':{}},'semantic':{}}
        if label not in sources:sources[label]=call('POST','sources',body)['id']
        identifier=sources[label]
        tested=call('POST','sources/'+identifier+'/test')
        check(label+'_readonly_credentials',tested.get('readonly_verified') is True)
        catalog=call('POST','sources/'+identifier+'/discover')
        check(label+'_object_discovered',obj in catalog['objects'])
        current=call('GET','sources/'+identifier)
        body['connection']=current['connection'];body['credential']=None
        body['policy']['objects']={obj:catalog['objects'][obj]}
        call('PUT','sources/'+identifier,body);call('POST','sources/'+identifier+'/activation',{'active':True})
        request={'object':obj,'limit':2,'query':{} if kind in ('mongodb','rest') else 'SELECT * FROM '+obj}
        result=call('POST','sources/'+identifier+'/query',request,headers=user_headers())
        check(label+'_real_read_bounded',result['row_count']==2 and result['incomplete'] is True and result['untrusted_data'] is True)
        check(label+'_sensitive_field_excluded','email' not in {c.lower() for c in result['columns']})
        denied=client.post('sources/'+identifier+'/query',json=request,headers=user_headers(OTHER))
        check(label+'_unauthorized_actor_denied',denied.status_code==404)
        restricted=client.post('sources/'+identifier+'/query',json=request,headers=user_headers(restriction=[]))
        check(label+'_per_key_source_restriction',restricted.status_code==404)
        forbidden_query={'object':obj,'query':{'filter':{'$where':'return true'}} if kind=='mongodb' else {'method':'POST'} if kind=='rest' else 'DELETE FROM '+obj}
        denied=client.post('sources/'+identifier+'/query',json=forbidden_query,headers=user_headers())
        check(label+'_write_or_unsafe_operator_denied',denied.status_code==422)
        if kind not in ('mongodb','rest'):
            denied=client.post('sources/'+identifier+'/query',json={'object':obj,'query':'SELECT '+('EMAIL' if kind=='oracle' else 'email')+' FROM '+obj},headers=user_headers())
            check(label+'_explicit_sensitive_column_denied',denied.status_code==422)
        admin_view=call('GET','sources/'+identifier)
        check(label+'_credential_never_returned','credential' not in admin_view and admin_view.get('credential_set') is (kind!='sqlite'))
    except Exception as error:failures.append({'source':label,'error_type':type(error).__name__,'detail':str(error)[:220]})

report={'passed':not failures and all(c['passed'] for c in checks),'scope':'Synthetic fixture databases only; TLS false on isolated test databases, never a production TLS bypass',
    'checks':checks,'failures':failures,'sources':sources}
text=json.dumps(report,ensure_ascii=False)
for field in ['admin_password','reader_password','token']:text=text.replace(fixture[field],'[REDACTED]')
print(text)
raise SystemExit(0 if report['passed'] else 1)
