"""Synthetic planner outputs exercise the boundary; no external database or LLM."""
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import HTTPException

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hub.orchestrator import answer,cross,count_plan,metadata

def source_row(identifier='a',unit='SJAM'):
    return {'id':identifier,'name':unit+' - Oracle SARH','kind':'oracle','description':'Synthetic',
        'semantic':{'organization':unit},'policy':{'objects':{'SARH.RH_CARGO':{'type':'table','fields':[{'name':'ID'}]}}}}

def test_exact_count_never_uses_llm_and_keeps_source_evidence():
    row=source_row()
    class Hub:
        store=SimpleNamespace()
        def __init__(self):self.store.sql=self.sql
        async def sql(self,*a):return [row]
        async def authorized(self,*a):return True
        async def organization_active(self,*a):return True
        async def relationships(self,*a):return []
        async def source(self,*a,**kw):return row
        async def llm(self,*a):raise AssertionError('Exact count unnecessarily used a model')
        async def execute(self,identifier,query,user):
            assert identifier=='a' and query.query=='SELECT COUNT(*) AS TOTAL FROM SARH.RH_CARGO'
            return {'source_id':'a','source_name':row['name'],'objects':['SARH.RH_CARGO'],'columns':['TOTAL'],'rows':[[42]],'row_count':1,'incomplete':False}
    result=asyncio.run(answer('Quantos registros existem na tabela SARH.RH_CARGO?','general',{},Hub(),['a']))
    assert '42' in result['answer'] and result['queries_executed']==1 and result['sources'][0]['id']=='a'

@pytest.mark.parametrize('question',[
    'Quantos ativos existem na tabela SARH.RH_CARGO?',
    'SELECT COUNT(*) FROM SARH.RH_CARGO WHERE ID=1',
    'Compare o total da SARH.RH_CARGO',
    'Quantos registros existem na tabela SARH.SECRET?',
    'Quantos registros existem por unidade na SARH.RH_CARGO?',
    'Quantos registros SARH.RH_CARGO com ID igual a 7?',
    'Quantos registros na SARH.RH_CARGO de tipo comissionado?',
])
def test_count_shortcut_does_not_drop_filters_or_read_unauthorized_tables(question):
    assert count_plan(question,[source_row()]) is None

def test_count_shortcut_needs_one_unambiguous_source():
    assert count_plan('Quantos registros na SARH.RH_CARGO?',[source_row('a'),source_row('b','SJTO')]) is None

def test_selected_source_or_sectional_cannot_fall_back_to_another_source():
    class Hub:
        store=SimpleNamespace()
        def __init__(self):self.store.sql=self.sql
        async def sql(self,*a):return [source_row('a')]
        async def authorized(self,*a):return True
        async def organization_active(self,*a):return True
        async def llm(self,*a):raise AssertionError('Unauthorized source reached model')
    for selected,question in [(['private'],'Count SARH'),(['a'],'Quantos registros em SJPI?')]:
        with pytest.raises(HTTPException) as error:asyncio.run(answer(question,'general',{},Hub(),selected))
        assert error.value.status_code==404

def test_question_object_is_not_lost_after_first_eight_catalog_entries():
    row=source_row();row['policy']['objects']={f'SARH.T{i}':{'type':'table','fields':[{'name':'ID'}]} for i in range(20)}
    assert 'SARH.T19' in metadata(row,'Quantos registros em SARH.T19?')['objects']


def test_missing_mapping_executes_no_queries_even_with_long_question():
    rows=[{'id':str(i),'name':'Fonte '+str(i),'kind':'postgres','description':'Synthetic',
           'semantic':{},'policy':{'objects':{'app.people':{'type':'table','fields':[{'name':'id'}]}}}} for i in (1,2)]
    class Hub:
        store=SimpleNamespace()
        def __init__(self):self.calls=0;self.store.sql=self.sql
        async def sql(self,*a):return rows
        async def authorized(self,*a):return True
        async def organization_active(self,*a):return True
        async def relationships(self,*a):return []
        async def execute(self,*a):raise AssertionError('Unapproved cross query executed')
        async def llm(self,body,user):
            assert body['tool_choice']['function']['name']=='plan_read_queries'
            assert body['parallel_tool_calls'] is False
            self.calls+=1
            return {'choices':[{'message':{'tool_calls':[{'function':{'name':'plan_read_queries','arguments':json.dumps({
                'steps':[{'source_id':r['id'],'object':'app.people','query':'SELECT id FROM app.people'} for r in rows],
                'relationship_id':'','criteria':'Synthetic comparison'})}}]}}]}
    hub=Hub()
    result=asyncio.run(answer('Compare '+' '.join('word'+str(n) for n in range(100)),'coding',{},hub))
    assert result['needs_mapping'] and result['queries_executed']==0 and hub.calls==1


def test_cross_requires_unique_non_null_keys():
    mapping={'id':'synthetic','left_field':'id','right_field':'id','criteria':'Exact IDs','compare_fields':[]}
    right={'columns':['id'],'rows':[[1]],'incomplete':False}
    for rows in ([[1],[1]],[[None]]):
        with pytest.raises(HTTPException) as error:
            cross({'columns':['id'],'rows':rows,'incomplete':False},right,mapping)
        assert error.value.status_code==409


def test_cross_never_coerces_keys_and_reports_truncation():
    mapping={'id':'synthetic','left_field':'id','right_field':'id','criteria':'Exact IDs','compare_fields':[]}
    result=cross({'columns':['id'],'rows':[[1]],'incomplete':True},
                 {'columns':['id'],'rows':[['1']],'incomplete':False},mapping)
    assert result['matched']==0 and result['incomplete']
    assert len(result['only_left'])==len(result['only_right'])==1
