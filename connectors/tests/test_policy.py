"""Security invariants for the bounded SQL and network boundary (synthetic only)."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common.policy import validate_sql,Rejected,validate_ip,pinned_ip,masked_query,safe_rows

POLICY={'objects':{'app.people':{'type':'table','fields':[{'name':'id'},{'name':'nome'},{'name':'email','sensitive':True}]},
    'app.balance':{'type':'table','fields':[{'name':'id'},{'name':'saldo_minutos'}]}},'allow_sensitive':False,'blocked_objects':[]}

@pytest.mark.parametrize('dialect',['postgres','mysql','mssql','oracle','sqlite'])
def test_select_and_expanded_star_respect_field_acl(dialect):
    query,objects=validate_sql(dialect,'SELECT * FROM app.people',POLICY)
    assert objects==['app.people'] and 'email' not in query.lower() and 'nome' in query.lower()
    with pytest.raises(Rejected):validate_sql(dialect,'SELECT email FROM app.people',POLICY)

@pytest.mark.parametrize('sql',[
    'DROP TABLE app.people','DELETE FROM app.people','UPDATE app.people SET nome=\'x\'',
    'INSERT INTO app.people VALUES(1,\'x\')','SELECT id INTO app.stolen FROM app.people',
    'SELECT id FROM app.people; SELECT id FROM app.people','COPY app.people TO PROGRAM \'id\'',
    'SELECT pg_sleep(10) FROM app.people','SELECT pg_read_file(\'/etc/passwd\') FROM app.people',
    'SELECT load_extension(\'x\') FROM app.people','SELECT id FROM app.people -- hidden instruction',
    'SELECT id FROM otherdb.app.people','SELECT id FROM people','SELECT * FROM app.secret',
    'WITH x AS (DELETE FROM app.people RETURNING id) SELECT id FROM x',
    'SELECT email AS nome FROM app.people','SELECT p.id FROM app.people p JOIN app.secret s ON p.id=s.id',
])
def test_writes_side_effects_comments_and_unauthorized_objects_are_rejected(sql):
    with pytest.raises(Rejected):validate_sql('postgres',sql,POLICY)

def test_authorized_join_and_aggregate_are_supported():
    sql,objects=validate_sql('postgres','SELECT p.nome, SUM(b.saldo_minutos) AS total FROM app.people p JOIN app.balance b ON p.id=b.id GROUP BY p.nome',POLICY)
    assert objects==['app.balance','app.people'] and 'SUM' in sql

def test_iso_date_constructor_is_bounded_to_valid_literal_dates():
    sql,_=validate_sql('oracle',"SELECT id FROM app.people WHERE DATE '2026-10-01' <= DATE '2026-10-31'",POLICY)
    assert '2026-10-01' in sql
    for value in ('2026-02-31','01-OCT-2026','2026-1-1'):
        with pytest.raises(Rejected):validate_sql('oracle',"SELECT id FROM app.people WHERE DATE '"+value+"' IS NOT NULL",POLICY)

@pytest.mark.parametrize('address',['127.0.0.1','::1','::ffff:127.0.0.1','169.254.169.254','0.0.0.0','224.0.0.1','10.92.0.5','172.19.5.250'])
def test_internal_metadata_and_infrastructure_addresses_are_rejected(address):
    with pytest.raises(Rejected):validate_ip(address,['10.92.0.0/16','172.19.5.250/32'])

def test_dns_rebinding_or_mixed_answer_is_denied(monkeypatch):
    import socket
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('192.168.50.11',5432))])
    with pytest.raises(Rejected):pinned_ip({'host':'fixture.invalid','port':5432,'approved_ips':['192.168.50.10']})

def test_masked_audit_does_not_retain_literals():
    result=masked_query('postgres',"SELECT nome FROM app.people WHERE nome='private-person' AND id=17219")
    assert 'private-person' not in result and '17219' not in result

def test_result_rows_and_cells_are_bounded_and_marked_untrusted():
    result=safe_rows(['nome'],[['x'*900]]*5,2)
    assert result['row_count']==2 and result['incomplete'] and result['untrusted_data']
    assert len(result['rows'][0][0])==512
