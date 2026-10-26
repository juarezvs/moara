"""Real synthetic database group/mapping/MCP/isolation acceptance inside the hub."""
import json
import sys
import uuid
from pathlib import Path
import httpx
fixture=json.load(sys.stdin);sources=fixture['sources'];checks={}
owner='local:00000000-0000-0000-0000-000000000111'
other='local:00000000-0000-0000-0000-000000000222'
key=Path('/run/secrets/connector_hub_key').read_text().strip()
client=httpx.Client(base_url='http://127.0.0.1:8070/v1/',headers={'Authorization':'Bearer '+key,'X-Actor-Id':owner,'X-Actor-Admin':'true'},timeout=45)
def check(name,value):
    checks[name]=bool(value)
    if not value:raise AssertionError(name)
def call(method,path,body=None,headers=None):
    response=client.request(method,path,json=body,headers=headers)
    if response.status_code>=400:raise RuntimeError('bounded_governance_request_failed')
    return response.json()
def user(subject):return {'X-Actor-Id':subject,'X-Actor-Admin':'false'}
def config(row,policy):return {k:row[k] for k in ['name','description','kind','connection','semantic']}|{'credential':None,'policy':policy}

def main():
    left=call('GET','sources/'+sources['pg-ponto']);right=call('GET','sources/'+sources['mysql'])
    check('fixtures_explicitly_identified',all(r['name'].startswith('_reconstruction_fixture_') for r in [left,right]))
    mapping=None;group=None;tls_source=None
    original=left['policy'];rest_settings=call('GET','types/rest/settings')
    try:
        body={'name':'_qa_explicit_mapping_'+uuid.uuid4().hex[:8],'left_source':left['id'],'left_object':'app.ponto','left_field':'id',
            'right_source':right['id'],'right_object':'rh.employees','right_field':'id',
            'compare_fields':[{'left':'saldo_minutos','right':'saldo_minutos'}],
            'criteria':'Synthetic IDs, exact integer equality, balances in minutes, bounded sample only.'}
        mapping=call('POST','relationships',body)
        result=call('POST','cross-query',{'relationship_id':mapping['id'],
            'left':{'object':'app.ponto','query':'SELECT id,saldo_minutos FROM app.ponto ORDER BY id','limit':2},
            'right':{'object':'rh.employees','query':'SELECT id,saldo_minutos FROM rh.employees ORDER BY id','limit':2}})
        check('actual_cross_database_comparison',result['matched']==2 and any(d['key']==2 for d in result['differences']))
        check('cross_sample_limits_explicit',result['incomplete'] and result['untrusted_data'])
        check('mapping_exact_delete_confirmation',client.request('DELETE','relationships/'+mapping['id'],json={'confirmation_name':'wrong'}).status_code==409)
        missing=str(uuid.uuid4())
        check('unapproved_mapping_denied',client.post('cross-query',json={'relationship_id':missing,'left':{'object':'app.ponto','query':'SELECT id FROM app.ponto'},'right':{'object':'rh.employees','query':'SELECT id FROM rh.employees'}}).status_code==409)
        group_name='_qa_group_'+uuid.uuid4().hex[:8]
        group=call('POST','groups',{'name':group_name,'owners':[other]})
        scoped={**original,'owners':[],'groups':[group['id']]}
        call('PUT','sources/'+left['id'],config(left,scoped));call('POST','sources/'+left['id']+'/activation',{'active':True})
        check('group_member_authorized',client.get('sources/'+left['id'],headers=user(other)).status_code==200)
        check('nonmember_denied',client.get('sources/'+left['id'],headers=user(owner)).status_code==404)
        check('referenced_group_delete_blocked',client.request('DELETE','groups/'+group['id'],json={'confirmation_name':group_name}).status_code==409)
        call('PUT','groups/'+group['id'],{'name':group_name,'owners':[]})
        check('membership_revocation_immediate',client.get('sources/'+left['id'],headers=user(other)).status_code==404)
        call('PUT','sources/'+left['id'],config(left,original));call('POST','sources/'+left['id']+'/activation',{'active':True})
        call('PUT','types/rest/settings',{'enabled':False,'timeout':rest_settings['timeout']})
        check('disabled_type_blocks_query',client.post('sources/'+sources['rest']+'/query',json={'object':'/employees','query':{},'limit':2}).status_code==503)
        call('PUT','types/rest/settings',{'enabled':rest_settings['enabled'],'timeout':rest_settings['timeout']})
        headers={'X-Actor-Id':owner,'X-Actor-Admin':'false'}
        result=call('POST','http://127.0.0.1:8070/mcp',{'jsonrpc':'2.0','id':1,'method':'tools/list'},headers)
        check('mcp_only_readonly_tools',len(result['result']['tools'])==2 and all(t['annotations']['readOnlyHint'] for t in result['result']['tools']))
        result=call('POST','http://127.0.0.1:8070/mcp',{'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'query_data_source','arguments':{'source_id':left['id'],'object':'app.ponto','query':'SELECT id FROM app.ponto','limit':2}}},headers)
        check('mcp_real_authorized_read',result['result']['isError'] is False)
        result=call('POST','http://127.0.0.1:8070/mcp',{'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'query_data_source','arguments':{'source_id':left['id'],'object':'app.ponto','query':'DELETE FROM app.ponto'}}},headers)
        check('mcp_write_rejected',result['result']['isError'] is True)
        import os
        endpoints=json.loads(os.environ.get('CONNECTOR_UPSTREAMS_JSON','null')) or {'postgres':'http://connector-postgres:8071'}
        check('direct_worker_requires_service_key',httpx.post(endpoints['postgres']+'/v1/call',json={},timeout=5).status_code in (401,403))
        worker_key=Path('/run/secrets/connector_postgres_key').read_text().strip()
        tls=httpx.post(endpoints['postgres']+'/v1/call',headers={'Authorization':'Bearer '+worker_key},json={
            'method':'test_connection','connection':{**left['connection'],'tls':True,'timeout':3},
            'credential':{'password':fixture['reader_password']},'policy':left['policy'],'request':{}},timeout=12)
        check('tls_required_never_falls_back_to_plaintext',tls.status_code>=400)
        return {'passed':True,'checks':checks,'scope':'actual synthetic PostgreSQL/MySQL/REST/group ACL/MCP; no corporate credentials or data'}
    finally:
        call('PUT','sources/'+left['id'],config(left,original));call('POST','sources/'+left['id']+'/activation',{'active':True})
        call('PUT','types/rest/settings',{'enabled':rest_settings['enabled'],'timeout':rest_settings['timeout']})
        if mapping:call('DELETE','relationships/'+mapping['id'],{'confirmation_name':body['name']})
        if group:call('DELETE','groups/'+group['id'],{'confirmation_name':group_name})

try:report=main()
except Exception as error:report={'passed':False,'checks':checks,'failure_type':type(error).__name__}
print(json.dumps(report));raise SystemExit(0 if report['passed'] else 1)
