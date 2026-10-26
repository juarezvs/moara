"""Shared SARH roles must never turn the integration into a write connection."""
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from worker import sql_driver as driver
from common.policy import Rejected,validate_sql

OPTIONS={'host':'oracle.test','port':1521,'database':'SARH','username':'integration',
    'timeout':5,'tls':False,'oracle_readonly_mode':'transaction',
    'oracle_role':'TRF_SARH_SERVIDOR','oracle_schema':'SARH'}

def test_shared_role_is_restricted_before_snapshot_and_connection_always_rolls_back(monkeypatch):
    events=[]
    db=SimpleNamespace(cursor=lambda:SimpleNamespace(execute=events.append),
        rollback=lambda:events.append('ROLLBACK'),close=lambda:events.append('CLOSE'))
    monkeypatch.setitem(sys.modules,'oracledb',SimpleNamespace(ConnectParams=lambda **kw:kw,connect=lambda **kw:db))
    monkeypatch.setattr(driver,'pinned_ip',lambda *args:'192.168.10.20')
    monkeypatch.delenv('ORACLE_CLIENT_MODE',raising=False)
    with pytest.raises(RuntimeError):
        with driver.connection('oracle',OPTIONS,{'password':'fixture'},[]):
            assert events==['SET ROLE "TRF_SARH_SERVIDOR"','SET TRANSACTION READ ONLY']
            raise RuntimeError('consumer failed')
    assert events[-2:]==['ROLLBACK','CLOSE']

def test_failed_readonly_snapshot_does_not_expose_connection(monkeypatch):
    events=[]
    def execute(sql):
        events.append(sql)
        if sql=='SET TRANSACTION READ ONLY':raise RuntimeError('snapshot refused')
    db=SimpleNamespace(cursor=lambda:SimpleNamespace(execute=execute),rollback=lambda:events.append('ROLLBACK'),close=lambda:events.append('CLOSE'))
    monkeypatch.setitem(sys.modules,'oracledb',SimpleNamespace(ConnectParams=lambda **kw:kw,connect=lambda **kw:db))
    monkeypatch.setattr(driver,'pinned_ip',lambda *args:'192.168.10.20')
    monkeypatch.delenv('ORACLE_CLIENT_MODE',raising=False)
    with pytest.raises(RuntimeError):
        with driver.connection('oracle',OPTIONS,{},[]):pytest.fail('Unsafe connection escaped')
    assert events[-2:]==['ROLLBACK','CLOSE']

@pytest.mark.parametrize('override',[{'oracle_role':''},{'oracle_schema':''},{'oracle_role':'x"; GRANT DBA TO x'}])
def test_institutional_mode_requires_explicit_validated_role_and_schema(monkeypatch,override):
    monkeypatch.setitem(sys.modules,'oracledb',SimpleNamespace())
    monkeypatch.setattr(driver,'pinned_ip',lambda *args:'192.168.10.20')
    with pytest.raises(Rejected):
        with driver.connection('oracle',{**OPTIONS,**override},{},[]):pytest.fail('Invalid scope accepted')

def test_shared_credentials_are_identified_honestly_and_admin_grants_still_denied(monkeypatch):
    monkeypatch.setattr(driver,'fetch',lambda *args:([],[('CREATE SESSION',),('ALTER SESSION',)]))
    result=driver.verify_privileges('oracle',object(),OPTIONS)
    assert result['readonly_verified'] and result['credential_readonly'] is False
    assert result['verification']=='oracle_readonly_transaction'
    monkeypatch.setattr(driver,'fetch',lambda *args:([],[('ALTER SYSTEM',)]))
    with pytest.raises(Rejected):driver.verify_privileges('oracle',object(),OPTIONS)

def test_credential_mode_is_not_silently_relaxed(monkeypatch):
    monkeypatch.setattr(driver,'fetch',lambda *args:([],[('ALTER SESSION',)]))
    with pytest.raises(Rejected):driver.verify_privileges('oracle',object())

@pytest.mark.parametrize('sql',[
    'DELETE FROM SARH.RH_CARGO','UPDATE SARH.RH_CARGO SET CARG_COD_CARGO=1',
    'ALTER SESSION SET CURRENT_SCHEMA=SYS','COMMIT','SET TRANSACTION READ WRITE',
    'SELECT SARH.FUNCAO_AUTONOMA() FROM SARH.RH_CARGO',
    "SELECT UTL_HTTP.REQUEST('https://example.com') FROM SARH.RH_CARGO",
    'SELECT * FROM SYS.USER$','SELECT * FROM SARH.RH_CARGO FOR UPDATE',
])
def test_oracle_writes_routines_and_other_schemas_are_rejected(sql):
    policy={'objects':{'SARH.RH_CARGO':{'type':'table','fields':[{'name':'CARG_COD_CARGO'}]}},'allow_sensitive':False}
    with pytest.raises(Rejected):validate_sql('oracle',sql,policy)

def test_sarh_catalog_is_schema_scoped_with_bound_parameter(monkeypatch):
    captured=[]
    def fetch(db,sql,params=(),max_rows=5000):
        captured.append((sql,params,max_rows));return [],[]
    monkeypatch.setattr(driver,'fetch',fetch)
    assert driver.discover('oracle',object(),OPTIONS)['objects']=={}
    assert 'AND c.OWNER=:1' in captured[0][0] and captured[0][1]==('SARH',)

def test_oracle_declared_composite_keys_preserve_position_and_catalog_scope(monkeypatch):
    calls=[]
    def fetch(db,sql,params=(),max_rows=5000):
        calls.append((sql,params))
        if 'ALL_TAB_COLUMNS' in sql:return [],[('SARH',t,'TABLE',f,'NUMBER','') for t in ('PARENT','CHILD') for f in ('ID','UNIT')]
        if "a.CONSTRAINT_TYPE='P'" in sql:return [],[('SARH','PARENT','UNIT','PK_PARENT',1),('SARH','PARENT','ID','PK_PARENT',2)]
        return [],[('SARH','CHILD','UNIT','SARH','PARENT','UNIT','FK_CHILD',1),('SARH','CHILD','ID','SARH','PARENT','ID','FK_CHILD',2),('SARH','CHILD','ID','PRIVATE','HIDDEN','ID','FK_HIDDEN',1)]
    monkeypatch.setattr(driver,'fetch',fetch)
    value=driver.discover('oracle',object(),OPTIONS)
    assert value['objects']['SARH.PARENT']['primary_key']==['UNIT','ID']
    assert [r['position'] for r in value['relationships']]==[1,2]
    assert all(r['column_count']==2 for r in value['relationships'])
    assert all(params==('SARH',) for _,params in calls)
    assert 'd.POSITION=b.POSITION' in calls[-1][0]
