"""Tenant isolation and immutable-view boundaries, using synthetic records only."""
import json,sqlite3,sys
from pathlib import Path
import pytest
from types import SimpleNamespace
from pydantic import ValidationError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common.secp_scope import definitions,public_columns
from common.source_selection import select
from common.contracts import Policy,Connection,compatible_worker_fields,KINDS
from common.policy import Rejected
from worker.sql_driver import check_views,view_fingerprint,verify_privileges
from worker import sql_driver
from hub.orchestrator import metadata,bounded_relationships

def test_oracle_composite_relationship_reaches_planner_only_as_a_complete_authorized_key():
    objects={name:{'type':'table','fields':[{'name':'ID'},{'name':'UNIT'}]} for name in ('SARH.CHILD','SARH.PARENT')}
    pairs=[{'from_object':'SARH.CHILD','from_field':f,'to_object':'SARH.PARENT','to_field':f,'constraint_name':'FK_CHILD','position':i,'column_count':2} for i,f in enumerate(('UNIT','ID'),1)]
    row={'id':'s','name':'Oracle','description':'','kind':'oracle','policy':{'objects':objects},'catalog':{'relationships':pairs},'semantic':{}}
    assert metadata(row)['relationships']==pairs
    assert bounded_relationships(pairs,objects,limit=1)==[]
    assert bounded_relationships(pairs[:1],objects)==[]
    objects['SARH.CHILD']['fields']=[{'name':'ID'}]
    assert metadata(row)['relationships']==[]

A='11111111-1111-4111-8111-111111111111';B='22222222-2222-4222-8222-222222222222';C='33333333-3333-4333-8333-333333333333'

@pytest.mark.parametrize('relative',['hub/main.py','worker/main.py'])
def test_service_entrypoint_compiles_before_rollout(relative):
    path=Path(__file__).resolve().parents[1]/relative
    compile(path.read_bytes(),str(path),'exec')

def fixture():
    tables={'orgaos':['id','sigla'],'servidores':['id','orgao_id','usuario_id','matricula','cpf'],
            'usuarios':['id','nome','senha_hash'],'unidades_organizacionais':['id','orgao_id','nome'],
            'lotacoes':['id','servidor_id','unidade_id'],'marcacoes':['id','servidor_id','data_referencia','latitude'],
            'face_mobile_sessions':['id','access_hash'],'solicitacoes':['id','servidor_id','descricao','dados_solicitados']}
    relations=[{'table_name':t,'column_name':f,'target_table':p,'target_column':'id'} for t,f,p in [
        ('servidores','orgao_id','orgaos'),('unidades_organizacionais','orgao_id','orgaos'),
        ('lotacoes','servidor_id','servidores'),('lotacoes','unidade_id','unidades_organizacionais'),
        ('marcacoes','servidor_id','servidores'),('solicitacoes','servidor_id','servidores')]]
    columns=[{'table_schema':'public','table_name':t,'column_name':f,'data_type':'jsonb' if f=='dados_solicitados' else 'text'} for t,fields in tables.items() for f in fields]
    db=sqlite3.connect(':memory:');db.execute("ATTACH DATABASE ':memory:' AS public")
    for t,fields in tables.items():db.execute('CREATE TABLE public.'+t+' ('+', '.join(f+' TEXT' for f in fields)+')')
    for i,unit in enumerate((A,B,C),1):
        db.execute('INSERT INTO public.orgaos VALUES (?,?)',(unit,'UNIT'+str(i)))
        db.execute('INSERT INTO public.servidores VALUES (?,?,?,?,?)',(str(i),unit,'u'+str(i),'m'+str(i),'private'))
        db.execute('INSERT INTO public.usuarios VALUES (?,?,?)',('u'+str(i),'person'+str(i),'private-hash'))
        db.execute('INSERT INTO public.unidades_organizacionais VALUES (?,?,?)',('s'+str(i),unit,'sector'+str(i)))
        db.execute('INSERT INTO public.lotacoes VALUES (?,?,?)',('l'+str(i),str(i),'s'+str(i)))
        db.execute('INSERT INTO public.marcacoes VALUES (?,?,?,?)',('e'+str(i),str(i),'2026-10-01','private'))
    return db,{'columns':columns,'relations':relations}

def test_database_view_scopes_single_unit_and_consolidated_exclude_inactive_records():
    db,catalog=fixture()
    try:
        for units,expected in ((A,{'1'}),([A,B],{'1','2'})):
            views,_=definitions(catalog,units)
            for table in ('servidores','marcacoes'):
                rows=db.execute(views[table]['query']).fetchall()
                assert {r[0].lstrip('e') for r in rows}==expected
            users=db.execute(views['usuarios']['query']).fetchall()
            assert {r[0].lstrip('u') for r in users}==expected
            assert 'face_mobile_sessions' not in views
            assert all('cpf' not in item['columns'] and 'senha_hash' not in item['columns'] and 'latitude' not in item['columns'] for item in views.values())
            assert views['solicitacoes']['columns']==['id','servidor_id']
    finally:db.close()

def test_pinned_definition_accepts_encapsulated_base_but_rejects_drift_and_functions():
    definition='SELECT t.id FROM public.servidores t WHERE t.orgao_id=\''+A+"'"
    objects={'analytics.people':{'type':'view','definition':definition,'fields':[{'name':'id'}]}}
    pins={'analytics.people':view_fingerprint(definition)}
    check_views('postgres',objects,['analytics.people'],pins)
    with pytest.raises(Rejected):check_views('postgres',objects,['analytics.people'])
    objects['analytics.people']['definition']=definition.replace(A,B)
    with pytest.raises(Rejected):check_views('postgres',objects,['analytics.people'],pins)
    malicious='SELECT pg_read_file(\'/etc/passwd\') FROM public.servidores'
    objects['analytics.people']['definition']=malicious
    with pytest.raises(Rejected):check_views('postgres',objects,['analytics.people'],{'analytics.people':view_fingerprint(malicious)})

def test_public_routines_exception_still_rejects_write_or_administrative_roles(monkeypatch):
    def fake(danger=None):
        def fetch(db,query,*args,**kwargs):
            if 'SELECT rolsuper' in query:return [],[(danger=='super',False,False,False,False)]
            if 'has_database_privilege' in query:return [],[(False,)]
            if 'has_function_privilege' in query:return [],[(1,)]
            if danger=='write' and 'has_table_privilege' in query:return [],[(1,)]
            return [],[]
        return fetch
    monkeypatch.setattr(sql_driver,'fetch',fake())
    with pytest.raises(Rejected):verify_privileges('postgres',None,{'postgres_readonly_mode':'credential'})
    value=verify_privileges('postgres',None,{'postgres_readonly_mode':'pinned_views'})
    assert value['readonly_verified'] and value['credential_readonly'] is False
    for danger in ('write','super'):
        monkeypatch.setattr(sql_driver,'fetch',fake(danger))
        with pytest.raises(Rejected):verify_privileges('postgres',None,{'postgres_readonly_mode':'pinned_views'})

def test_pin_contract_cannot_approve_an_unlisted_object_or_invalid_fingerprint():
    for pins in ({'other.table':'a'*64},{'app.people':'not-a-digest'}):
        with pytest.raises(ValidationError):Policy(objects={'app.people':{'fields':[{'name':'id'}]}},view_hashes=pins)

def test_routing_chooses_application_unit_or_consolidated_and_preserves_sarh_queries():
    oracle={'id':'oracle','kind':'oracle','semantic':{'organization':'SJAM'}}
    unit={'id':'unit','kind':'postgres','semantic':{'organization':'SJAM','dataset':'secp_application'}}
    global_source={'id':'global','kind':'postgres','semantic':{'organization_scope':['SJAM','SJTO'],'dataset':'secp_application'}}
    rows=[oracle,unit,global_source]
    assert select('Quais férias no SECP da SJAM?',rows)==[unit]
    assert select('Quantas solicitações no SECP?',rows)==[global_source]
    assert select('Compare SJAM e SJTO no SECP',rows)==[global_source]
    assert select('Liste servidores afastados hoje na SJAM',rows)==[oracle]
    assert select('Quais fontes Oracle posso consultar?',rows)==[oracle]
    assert select('Consulte SECP da SJPI',rows)==[]
    assert select('Quantas férias no SECP?',[unit])==[unit]

def test_catalog_budget_and_real_join_keys_are_preserved_without_credentials():
    row={'id':'s','name':'SECP','kind':'postgres','description':'Functional','semantic':{'dataset':'secp_application','schema':'a',
         'join_keys':[['t1','parent_id','t2','id']],'password':'must-not-be-forwarded'},
         'policy':{'objects':{'a.t'+str(i):{'type':'view','fields':[{'name':'long_column_name_'+str(j),'type':'character varying(500)'} for j in range(60)]} for i in range(12)}}}
    value=metadata(row,'a.t1 a.t2')
    assert len(json.dumps(value,ensure_ascii=True))<=12000
    assert value['relationships']==[{'from_object':'a.t1','from_field':'parent_id','to_object':'a.t2','to_field':'id'}]
    assert 'must-not-be-forwarded' not in json.dumps(value)

def test_consolidated_catalog_includes_orgs_and_real_parents_for_business_filters():
    objects={'a.events':{'type':'view','fields':[{'name':'servidor_id'}]},
             'a.servidores':{'type':'view','fields':[{'name':'id'},{'name':'orgao_id'}]},
             'a.orgaos':{'type':'view','fields':[{'name':'id'},{'name':'sigla'}]}}
    objects.update({'a.other'+str(i):{'type':'view','fields':[{'name':'status'}]} for i in range(20)})
    row={'id':'s','name':'SECP','kind':'postgres','description':'Functional',
         'semantic':{'dataset':'secp_application','schema':'a','organization_scope':['SJAM','SJTO'],
                     'join_keys':[['events','servidor_id','servidores','id'],['servidores','orgao_id','orgaos','id']]},'policy':{'objects':objects}}
    value=metadata(row,'Compare a.events entre SJAM e SJTO no SECP')
    assert {'a.events','a.servidores','a.orgaos'}<=value['objects'].keys()
    assert len(value['relationships'])==2

@pytest.mark.parametrize('kind',KINDS)
def test_new_postgres_contract_never_breaks_existing_strict_connector_workers(kind):
    connection=Connection().model_dump();policy=Policy().model_dump()
    wire_connection,wire_policy=compatible_worker_fields(kind,connection,policy)
    assert ('postgres_readonly_mode' in wire_connection)==(kind=='postgres')
    assert ('view_hashes' in wire_policy)==(kind=='postgres')
    assert 'postgres_readonly_mode' in connection and 'view_hashes' in policy

def test_postgres_connection_enforces_readonly_before_queries_and_checks_actual_mode(monkeypatch):
    import psycopg
    for actual in ('on','off'):
        calls=[]
        class Database:
            def execute(self,query,*args):calls.append(query);return SimpleNamespace(fetchone=lambda:(actual,))
            def rollback(self):calls.append('rollback')
            def close(self):calls.append('close')
        monkeypatch.setattr(psycopg,'connect',lambda **kwargs:Database())
        monkeypatch.setattr(sql_driver,'pinned_ip',lambda *args:'192.0.2.1')
        c=Connection(host='fixture.invalid',port=5432,database='fixture',username='reader',tls=False).model_dump()
        if actual=='off':
            with pytest.raises(Rejected):
                with sql_driver.connection('postgres',c,{},[]):pass
        else:
            with sql_driver.connection('postgres',c,{},[]):calls.append('query_allowed')
            assert calls.index('SHOW transaction_read_only')<calls.index('query_allowed')
        assert calls[0]=='SET TRANSACTION READ ONLY' and calls[-2:]==['rollback','close']
