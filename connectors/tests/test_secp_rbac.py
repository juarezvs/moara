"""Authorization is applied before aggregation, and cannot inherit Moara admin."""
import asyncio,json,subprocess,sys,uuid
from pathlib import Path
from types import SimpleNamespace
import pytest,sqlglot
from sqlglot import exp
from fastapi import HTTPException
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from worker.secp_scope import policy_for,scoped_sql,descriptor,table_scopes
from worker.sql_driver import run
from common.policy import validate_sql,Rejected
from common.secp_access import revalidate

SCHEMA='moara_secp_sjam';ORG=str(uuid.uuid4());OWN=str(uuid.uuid4());OTHER=str(uuid.uuid4())
C={'username':SCHEMA+'_ro','postgres_readonly_mode':'pinned_views'}
POLICY={'objects':{SCHEMA+'.'+name:{'type':'view','fields':[{'name':f} for f in fields]} for name,fields in {
 'servidores':['id','usuario_id','orgao_id','matricula','nome_funcional','funcao_atual_descricao','ativo'],
 'orgaos':['id','sigla','nome','ativo'], 'banco_horas_saldos':['id','servidor_id','saldo_minutos'],
 'solicitacoes':['id','servidor_id','status'], 'usuarios':['id','matricula','nome','ativo']}.items()},'view_hashes':{}}
RELATIONS=[{'origin':'servidores','field':'orgao_id','target':'orgaos','key':'id'},
 {'origin':'banco_horas_saldos','field':'servidor_id','target':'servidores','key':'id'},
 {'origin':'solicitacoes','field':'servidor_id','target':'servidores','key':'id'}]
def grant(permissions):
 return {'permissions':permissions,'organizations':[{'id':ORG,'sigla':'SJAM'}],
  'relations':RELATIONS,'vectors':{'own':[OWN],'team':[OTHER],'own_units':[],'team_units':[]},
  'fingerprint':'fixed','profile_id':'synthetic','profile':'SERVIDOR'}

def test_own_scope_is_a_filtered_relation_before_count_and_grouping():
 g=grant(['banco-horas:consultar:proprio']);p,r=policy_for(C,POLICY,g)
 sql,used=validate_sql('postgres','SELECT COUNT(*) FROM '+SCHEMA+'.banco_horas_saldos',p)
 scoped,parameters,deps=scoped_sql(sql,C,POLICY,g,r)
 tree=sqlglot.parse_one(scoped,read='postgres')
 assert tree.find(exp.Count) and tree.find(exp.Exists)
 assert OWN not in scoped and [OWN] in parameters and [OTHER] not in parameters
 assert SCHEMA+'.servidores' in deps
 assert tree.find(exp.From).this.find(exp.Where) is not None

def test_supporting_employee_dimension_does_not_grant_private_resource_fields():
 g=grant(['banco-horas:consultar:proprio']);p,r=policy_for(C,POLICY,g)
 assert SCHEMA+'.solicitacoes' not in p['objects']
 assert 'funcao_atual_descricao' not in {f['name'] for f in p['objects'][SCHEMA+'.servidores']['fields']}
 with pytest.raises(Rejected):validate_sql('postgres','SELECT funcao_atual_descricao FROM '+SCHEMA+'.servidores',p)

def test_another_section_and_an_empty_rbac_are_denied():
 g=grant(['servidores:consultar:global']);g['organizations']=[{'id':str(uuid.uuid4()),'sigla':'SJTO'}]
 assert not policy_for(C,POLICY,g)[0]['objects']
 assert not policy_for(C,POLICY,grant([]))[0]['objects']

@pytest.mark.parametrize('query',[
 'SELECT COUNT(*) FROM {s}.servidores s',
 'SELECT COUNT(*) FROM {s}.servidores s CROSS JOIN {s}.banco_horas_saldos b',
 'SELECT COUNT(*) FROM {s}.servidores s LEFT JOIN {s}.banco_horas_saldos b ON b.servidor_id=s.id',
 'SELECT COUNT(*) FROM {s}.servidores s JOIN {s}.banco_horas_saldos b ON b.servidor_id=s.id OR TRUE',
 'SELECT COUNT(*) FROM {s}.servidores s JOIN {s}.banco_horas_saldos b ON NOT (b.servidor_id=s.id)',
 'WITH s AS (SELECT id FROM {s}.servidores) SELECT COUNT(*) FROM s JOIN {s}.banco_horas_saldos b ON b.servidor_id=s.id',
])
def test_supporting_global_dimension_cannot_be_queried_as_employee_register(query):
 from common.secp_joins import validate_support_joins
 p,_=policy_for(C,POLICY,grant(['banco-horas:consultar:global']))
 assert p['objects'][SCHEMA+'.servidores']['support_only']
 with pytest.raises(Rejected):validate_support_joins(query.format(s=SCHEMA),p,RELATIONS)

def test_supporting_global_dimension_can_join_its_authorized_primary_dataset():
 from common.secp_joins import validate_support_joins
 p,_=policy_for(C,POLICY,grant(['banco-horas:consultar:global']))
 validate_support_joins('SELECT COUNT(*) FROM '+SCHEMA+'.servidores s JOIN '+SCHEMA+'.banco_horas_saldos b ON b.servidor_id=s.id',p,RELATIONS)

def test_execution_read_permission_does_not_grant_payroll_or_workflow_budget_access():
 g=grant(['horas-extras:visualizar-execucao:global'])
 assert table_scopes(g,'horas_extras_execucoes_intervalos')=={'global'}
 assert not table_scopes(g,'horas_extras_calculos')
 assert not table_scopes(g,'overtime_budget_movements')
 g['permissions'].append('horas-extras:visualizar-folha:seccional')
 assert table_scopes(g,'horas_extras_calculos')=={'seccional'}

def test_team_plus_own_requires_both_explicit_permissions():
 for permissions,expected in [(['banco-horas:consultar:chefia'],[OTHER]),(['banco-horas:consultar:chefia','banco-horas:consultar:proprio'],sorted([OWN,OTHER]))]:
  g=grant(permissions);p,r=policy_for(C,POLICY,g)
  sql,_=validate_sql('postgres','SELECT COUNT(*) FROM '+SCHEMA+'.banco_horas_saldos',p)
  _,values,_=scoped_sql(sql,C,POLICY,g,r)
  assert expected in values

def test_literals_and_aliases_cannot_become_scope_parameters_or_escape_wrappers():
 g=grant(['servidores:consultar:global']);p,r=policy_for(C,POLICY,g)
 sql,_=validate_sql('postgres',"SELECT s.id FROM "+SCHEMA+".servidores s WHERE s.matricula LIKE '%:moara_scope_0%' OR TRUE",p)
 scoped,values,_=scoped_sql(sql,C,POLICY,g,r)
 assert '%:moara_scope_0%' in scoped and '$1' in scoped and values==[[ORG]]
 assert 'rbac_base' in scoped and 'EXISTS' in scoped

def test_worker_requires_verified_identity_even_for_a_moara_administrator():
 with pytest.raises(Rejected,match='identidade institucional'):
  run('postgres',{'connection':C,'method':'execute_readonly_query','policy':POLICY,'request':{'query':'SELECT 1'}},())

def test_directory_changed_in_moara_cannot_impersonate_a_secp_user(tmp_path,monkeypatch):
 from worker.secp_rbac import evaluate
 config=tmp_path/'secp.json';config.write_text(json.dumps({'connection':C,'directory_pins':{'SJAM':['a'*64]}}))
 monkeypatch.setenv('SECP_RBAC_CONFIG',str(config))
 with pytest.raises(Rejected,match='diretório'):
  evaluate({'organization':'SJAM','username':'synthetic','issuer':'b'*64})

def test_stored_result_is_denied_after_secp_scope_revocation():
 class Hub:
  async def source(self,*args,**kwargs):return {'_secp_access':{'fingerprint':'new'}}
 with pytest.raises(HTTPException) as error:
  asyncio.run(revalidate(Hub(),[{'source_id':'synthetic','secp_access':{'fingerprint':'old'}}],{}))
 assert error.value.status_code==403

def profile(code,permissions,*,identifier=None,excecao=False,destination=None):
 return {'id':identifier or code,'codigo':code,'nome':code,'ativo':True,'administrativo':code=='MASTER','excecao':excecao,
  'global':code=='MASTER','perfilDestinoExcecaoId':destination,'orgaoId':ORG,'orgao':{'id':ORG,'sigla':'SJAM','nome':'Synthetic'},
  'permissoes':[{'permissaoId':v,'permissao':{'codigo':v}} for v in permissions],'permissoesSeccionais':[]}
def snapshot(profiles,code=None):
 return {'username':'synthetic','profile':code,'user':{'id':OWN,'matricula':'synthetic','nome':'','tipo':'SERVIDOR','ativo':True,
  'servidor':{'orgaoId':ORG},'perfis':[{'orgaoId':ORG,'orgao':p['orgao'],'perfil':p} for p in profiles]},
  'permissions':[{'id':v,'codigo':v,'recurso':v.split(':')[0]} for v in ['banco-horas:consultar:proprio','servidores:consultar:global']],
  'organizations':[{'id':ORG,'sigla':'SJAM','nome':'Synthetic','ativo':True}],'releases':[],'substitutions':[]}
def resolve(data):
 bundle=Path(__file__).resolve().parents[1]/'secp_rbac/resolver.cjs'
 return subprocess.run(['node',str(bundle)],input=json.dumps(data),capture_output=True,text=True,timeout=30)

def test_real_secp_resolver_defaults_to_personal_profile_and_never_unions_master():
 data=snapshot([profile('SERVIDOR',['banco-horas:consultar:proprio']),profile('MASTER',[])])
 result=json.loads(resolve(data).stdout)
 assert result['profile']=='SERVIDOR' and 'servidores:consultar:global' not in result['permissions']
 data['profile']='MASTER';result=json.loads(resolve(data).stdout)
 assert result['global'] and 'servidores:consultar:global' in result['permissions']
 data['profile']='UNASSIGNED';assert resolve(data).returncode!=0

def test_real_secp_resolver_applies_section_denies_and_routine_release_overrides():
 p=profile('CUSTOM',['servidores:consultar:global','banco-horas:consultar:proprio'])
 p['permissoesSeccionais']=[{'orgaoId':ORG,'permissaoId':'servidores:consultar:global','permitida':False,'permissao':{'codigo':'servidores:consultar:global'}}]
 data=snapshot([p]);data['releases']=[{'tipo':'ROTINA','chave':'banco-horas','liberada':False}]
 assert json.loads(resolve(data).stdout)['permissions']==[]
 data['releases'].append({'tipo':'PERMISSAO','chave':'banco-horas:consultar:proprio','liberada':True})
 assert json.loads(resolve(data).stdout)['permissions']==['banco-horas:consultar:proprio']

def test_real_secp_resolver_never_inherits_master_from_an_automatic_substitution():
 data=snapshot([profile('SERVIDOR',[])])
 data['substitutions']=[{'unidadeId':ORG,'titularServidor':{'gestores':[],'usuario':{'perfis':[{'orgao':{'id':ORG,'sigla':'SJAM','nome':'Synthetic'},'perfil':profile('MASTER',[])}]}}}]
 result=json.loads(resolve(data).stdout)
 assert result['profile']=='SERVIDOR' and all(p['code']!='MASTER' for p in result['profiles'])
