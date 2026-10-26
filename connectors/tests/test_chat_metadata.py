import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hub.chat_metadata import answer

def rows():
    return [{'id':unit,'name':unit+' - Oracle SARH','kind':'oracle',
        'policy':{'objects':{'SARH.RH_CARGO':{'type':'table','fields':[{'name':'ID'}]}}}}
        for unit in ('SJAM','SJTO')]

def test_lists_actual_sources_and_authorized_tables_without_model():
    for prompt in ('Quais fontes Oracle posso consultar?','quais fontes de dados posso consultar'):
        value=answer(prompt,rows())
        assert len(value['sources'])==2 and 'SJAM' in value['answer'] and 'SJTO' in value['answer']
    value=answer('Liste as tabelas disponíveis da SJAM.',rows()[:1])
    assert 'SARH.RH_CARGO' in value['answer'] and 'SJTO' not in value['answer']
    assert value['execution_mode']=='authorized_catalog'

def test_catalog_does_not_invent_objects_or_answer_data_queries():
    assert answer('Quais fontes Oracle posso consultar?',[])['sources']==[]
    assert answer('Mostre os registros de servidores da SJAM.',rows()) is None
    assert answer('Quantos registros na tabela SARH.RH_CARGO da SJAM?',rows()) is None
