import asyncio
import sqlite3
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import pytest
import sqlglot
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hub.personnel_analytics import FIELDS,answer,closed_policy,intent,period,queries,sector,quoted
from common.policy import validate_sql

def catalog():
    return {name:{'type':'table','fields':[{'name':f,'type':'NUMBER' if f.endswith('FUNCIONARIO') or 'C_P_F' in f else 'VARCHAR2'} for f in fields]} for name,fields in FIELDS.items()}

@pytest.mark.parametrize('text,expected',[
    ('de 01/10/2026 a 31/10/2026',(date(2026,10,1),date(2026,10,31))),
    ('em outubro de 2026',(date(2026,10,1),date(2026,10,31))),
    ('hoje',(date(2026,10,21),date(2026,10,21))),
    ('mês passado',(date(2026,9,1),date(2026,9,30))),
    ('sem período',None),
])
def test_periods(text,expected):assert period(text,date(2026,10,21))==expected

def test_bad_periods_and_sector_extraction():
    for text in ('de 31/10/2026 a 01/10/2026','31/02/2026'):
        with pytest.raises(ValueError):period(text)
    assert sector('Quantas pessoas afastadas no setor NUTEC da SJAM em outubro de 2026?')=='NUTEC'
    assert sector('Quantas pessoas afastadas no NUTEC da SJAM em outubro de 2026?')=='NUTEC'
    assert intent('Mostre meu contracheque')=='payroll'
    assert intent('Liste servidores afastados de 01/10/2026 a 31/10/2026')=='absence'

def setup_db():
    db=sqlite3.connect(':memory:');db.execute("ATTACH DATABASE ':memory:' AS SARH")
    # sqlglot renders Oracle DATE literals as STR_TO_DATE in this SQLite
    # version. This fixture supports only the ISO constructor used by the SQL.
    db.create_function('STR_TO_DATE',2,lambda value,fmt:date.fromisoformat(value).isoformat())
    for table,fields in FIELDS.items():db.execute('CREATE TABLE '+table+' ('+', '.join(f+' '+('INTEGER' if f.endswith('FUNCIONARIO') or 'C_P_F' in f else 'TEXT') for f in fields)+')')
    def put(table,**values):db.execute('INSERT INTO '+table+' ('+','.join(values)+') VALUES ('+','.join('?' for _ in values)+')',list(values.values()))
    for code,cpf in ((1,111),(2,222),(3,333),(4,222)):
        put('SARH.RH_FUNCIONARIO',FUNC_SESB_SIGLA_SECAO_SUBSECAO='AM',FUNC_COD_FUNCIONARIO=code,FUNC_PESS_C_P_F=cpf)
    for cpf in (111,222,333):put('SARH.RH_PESSOAL',PESS_C_P_F=cpf,PESS_NOME='Person '+str(cpf))
    for code,start,end in ((1,'2026-01-01','2026-01-05'),(2,'2026-01-15',None),(2,'2026-01-17','2026-01-25'),(3,'2026-02-01',None),(3,'2026-01-25','2026-01-01'),(4,'2026-01-19','2026-01-21')):
        put('SARH.RH_AFASTAMENTOS_DIVERSOS',AFAD_FUNC_SIGLA_FUNCIONARIO='AM',AFAD_FUNC_COD_FUNCIONARIO=code,AFAD_DAT_INICIO_AFAST=start,AFAD_DAT_FIM_AFAST=end)
    for code,unit,start,end in ((1,10,'2026-01-01','2026-01-10'),(1,20,'2026-01-11',None),(2,20,'2025-01-01',None),(3,20,'2025-01-01',None),(4,20,'2025-01-01',None)):
        put('SARH.RH_HIST_LOTACAO',HLOT_FUNC_SIGLA_SECAO_SUBSECAO='AM',HLOT_FUNC_COD_FUNCIONARIO=code,HLOT_LOTA_COD_LOTACAO=unit,HLOT_DAT_INIC_LOTACAO=start,HLOT_DAT_FIM_LOTACAO=end)
    return db,put

def run(db,sql):
    validated,_=validate_sql('oracle',sql,closed_policy(catalog()))
    sqlite=sqlglot.transpile(validated,read='oracle',write='sqlite')[0]
    return db.execute(sqlite).fetchall()

def test_counts_people_not_events_and_checks_simultaneous_historical_posting():
    db,put=setup_db()
    try:
        count,listing=queries(date(2026,1,1),date(2026,1,31),20)
        assert run(db,count)[0][0]==1 # repeated events/jobs, one person; employee 1 moved later
        rows=run(db,listing)
        assert rows and all(row[1] in (2,4) for row in rows)
        put('SARH.RH_LICENCA',LICE_FUNC_SIGLA_SECAO_SUBSECAO='AM',LICE_FUNC_COD_FUNCIONARIO=1,LICE_COD_LICENCA=7)
        put('SARH.RH_PERIODO_LICENCA',PLIC_LICE_SECAO_SUBSECAO='AM',PLIC_LICE_COD_FUNCIONARIO=1,PLIC_LICE_COD_LICENCA=7,PLIC_INICIO_PERIODO='2026-01-28',PLIC_FIM_PERIODO='2026-01-30')
        assert run(db,count)[0][0]==2
        assert run(db,queries(date(2026,1,5),date(2026,1,5),10)[0])[0][0]==1
    finally:db.close()

def test_private_identity_keys_never_appear_in_list_projection_or_general_policy():
    c=catalog();p=closed_policy(c)
    listing=queries(date(2026,1,1),date(2026,1,31))[1]
    assert 'C_P_F' not in listing.split(' FROM ',1)[0]
    assert 'allow_sensitive' not in c
    assert p['audit']=='hash_only'
    assert len(sqlglot.parse('SELECT * FROM SARH.RH_LOTACAO WHERE LOTA_SIGLA_LOTACAO='+quoted("X'; DELETE FROM T;--"),read='oracle'))==1

def test_payroll_uses_existing_personal_portal_without_matricula_or_admin_override():
    async def check():
        value=await answer('Mostre meu contracheque de outubro de 2026',[],{},None)
        assert value['execution_mode']=='personal_payroll_portal'
        assert 'https://secp.am.trf1.gov.br/meu-contracheque?competencia=2026-10' in value['answer']
        assert 'matricula=' not in value['answer'] and not value['sources']
        denied=await answer('Liste servidores afastados hoje',[],{'admin':False},None)
        assert denied['execution_mode']=='personnel_access_denied'
    asyncio.run(check())

def test_unconfigured_filters_and_personal_requests_never_run_a_broader_query():
    async def check():
        for prompt in ('Liste somente servidores ativos afastados hoje na SJAM.',
                       'Quantas pessoas afastadas por doença hoje na SJAM?',
                       'Compare afastamentos por setor na SJAM em outubro de 2026.',
                       'Liste licenças da SJAM em outubro de 2026.',
                       'Mostre meus afastamentos em outubro de 2026.'):
            value=await answer(prompt,[],{'admin':True},None)
            assert value['execution_mode']=='personnel_clarification' and not value['sources']
    asyncio.run(check())

def test_real_authorization_is_rechecked_before_every_worker_query():
    from fastapi import HTTPException
    async def check(revoke=False,changed=False):
        row={'id':'synthetic','name':'SJAM','updated_at':1,'semantic':{'personnel_analytics':{'enabled':True}},
             'catalog':{'objects':catalog()},'connection':{},'credential':None}
        calls=[];audits=[]
        async def source(*args,**kwargs):return row
        async def authorize(*args,**kwargs):
            assert kwargs=={'personnel':True};calls.append('authorize')
            if revoke:raise HTTPException(403,'revoked')
            return dict(row,updated_at=2) if changed else row
        async def worker(*args,**kwargs):
            calls.append('worker');assert kwargs['policy']['audit']=='hash_only'
            return {'rows':[[2,0]],'row_count':1,'incomplete':False}
        async def audit(*args,**kwargs):audits.append(kwargs)
        hub=SimpleNamespace(source=source,authorize_execution=authorize,worker=worker,audit=audit,store=SimpleNamespace(decrypt=lambda value:{}))
        if revoke or changed:
            with pytest.raises(HTTPException):await answer('Quantas pessoas afastadas na SJAM em outubro de 2026?', [row], {'admin':True},hub)
            assert calls==['authorize']
        else:
            value=await answer('Quantas pessoas afastadas na SJAM em outubro de 2026?', [row], {'admin':True},hub)
            assert value['execution_mode']=='validated_personnel_analysis' and '**2 pessoas distintas**' in value['answer']
            assert calls==['authorize','worker'] and audits[0]['mode']=='hash_only'
    for revoked,changed in ((False,False),(True,False),(False,True)):asyncio.run(check(revoked,changed))
