"""Enforce table permissions and row scopes before SQL aggregation or pagination."""
from collections import deque
from copy import deepcopy
import json
import hashlib
import sqlglot
from sqlglot import exp
from common.policy import Rejected,IDENTIFIER,allowed_objects

DIMENSIONS={'servidores':{'id','usuario_id','orgao_id','matricula','nome_funcional','ativo'},
 'usuarios':{'id','matricula','nome','ativo'},'orgaos':{'id','sigla','nome','ativo'},
 'unidades_organizacionais':{'id','orgao_id','unidade_pai_id','sigla','nome','ativo'},
 'lotacoes':{'id','servidor_id','unidade_id','status','data_inicio','data_fim'},
 'cargos':{'id','descricao','ativo'},'categorias_pessoas':{'id','codigo','nome','ativo'}}
HR={'servidores','afastamentos','apuracao','marcacoes','banco-horas','solicitacoes','programacao-ferias','homologacao','minha-equipe','relatorios-gerenciais','recesso','acompanhamento-estagio'}

def resource(table):
    exact={'servidores':'servidores','usuarios':'usuarios','orgaos':'localidade','cargos':'servidores','categorias_pessoas':'servidores','lotacoes':'servidores','unidades_organizacionais':'unidades',
        'afastamentos_sarh':'afastamentos','gestores_unidades':'minha-equipe','estagios_supervisoes':'acompanhamento-estagio',
        'funcoes_confianca_referencias':'substituicoes-funcao','calendarios_institucionais':'calendario','tipos_feriados_suspensoes':'calendario',
        'estados':'localidade','cidades':'localidade','fusos_horarios':'localidade','regulamentacoes_ponto_orgaos':'regulamentacao-ponto',
        'processamentos_espelho_ponto':'apuracao','ocorrencias_frequencia':'apuracao','dispensas_ponto_servidores':'servidores'}
    if table in exact:return exact[table]
    for prefix,value in [('programacoes_ferias','programacao-ferias'),('jornadas','jornadas'),('escalas','jornadas'),
        ('marcacoes','marcacoes'),('apuracoes','apuracao'),('banco_horas','banco-horas'),('solicitacoes','solicitacoes'),
        ('fechamentos_mensais','homologacao'),('homologacoes','homologacao'),('boletins','boletim-frequencia'),
        ('procedimentos_administrativos','procedimentos-frequencia'),('acompanhamentos_estagio','acompanhamento-estagio'),
        ('recessos','recesso'),('substituicoes','substituicoes-funcao'),('pagamentos_substituicoes','substituicoes-funcao'),
        ('autorizacoes_horas_extras','horas-extras'),('horas_extras','horas-extras'),('overtime_','horas-extras'),
        ('mct_politicas','mct-politicas'),('mct_configuracoes','mct-configuracao'),('mct_rubricas','mct-rubricas'),
        ('mct_naturezas','mct-rubricas'),('mct_regras','mct-regras'),('mct_','mct-simulador')]:
        if table.startswith(prefix):return value
    return None

def scopes(grant,recurso,actions_override=None):
    result=set()
    actions={'consultar','visualizar'}
    # These resources have management screens rather than separate read grants.
    if recurso in {'jornadas','unidades','calendario','regulamentacao-ponto'}:actions.add('gerenciar')
    if recurso=='substituicoes-funcao':actions.add('relatorio')
    if recurso=='homologacao':actions.add('gerenciar')
    if recurso=='boletim-frequencia':actions.add('gerar')
    if recurso in {'solicitacoes','recesso'}:actions.add('analisar' if recurso=='solicitacoes' else 'homologar')
    if actions_override is not None:actions=actions_override
    for code in grant['permissions']:
        parts=code.rsplit(':',2)
        if len(parts)==3 and parts[0]==recurso and parts[1] in actions:result.add(parts[2])
    return result & {'global','seccional','master','chefia','subordinados','proprio'}

def table_scopes(grant,table):
    if table.startswith(('horas_extras_calculos','overtime_payroll')):
        return scopes(grant,'horas-extras',{'visualizar-folha'})
    if table.startswith(('overtime_budget','overtime_project','overtime_extraordinary')) and not grant.get('global'):
        # Campaign/workflow responsibility predicates are not generalized to
        # all records merely because a user can operate one assigned workflow.
        return set()
    if table.startswith(('horas_extras_','autorizacoes_horas_extras','overtime_')):
        actions={'visualizar','visualizar-execucao'}
        if table.startswith(('overtime_polic','overtime_rate')):actions={'configurar-politica'}
        elif table.startswith('overtime_workflow'):actions={'configurar-workflow'}
        elif table=='overtime_responsibility_assignments':actions={'configurar-responsaveis'}
        elif table.startswith(('overtime_budget','overtime_project','overtime_extraordinary')):actions={'responder-orcamento','visualizar-execucao'}
        return scopes(grant,'horas-extras',actions)
    return scopes(grant,resource(table))

def scope_kind(scopes):
    if scopes & {'global','seccional','master'}:return 'organization'
    if scopes & {'chefia','subordinados'}:return 'team'
    if 'proprio' in scopes:return 'own'
    return None

def source_schema(connection):
    user=connection['username']
    if not user.startswith('moara_secp_') or not user.endswith('_ro'):raise Rejected('A fonte não é um acesso SECP autorizado')
    schema=user[:-3]
    if not IDENTIFIER.fullmatch(schema) or schema=='moara_secp_rbac':raise Rejected('A fonte não é um acesso SECP autorizado')
    return schema

def path_to(origin,target,objects,relations):
    if origin==target:return []
    # Users are a dimension of their own functional records; this reverse link
    # is exact, not a name/email association.
    edges=relations+[{'origin':'usuarios','field':'id','target':'servidores','key':'usuario_id'}]
    queue=deque([(origin,[])]);seen={origin}
    while queue:
        current,path=queue.popleft()
        for r in sorted((r for r in edges if r['origin']==current),key=lambda r:(r['target']!=target,r['field'])):
            nxt=r['target']
            if nxt=='usuarios' or nxt not in objects or current not in objects:continue
            if r['field'] not in objects[current] or r['key'] not in objects[nxt]:continue
            if nxt==target:return path+[r]
            if nxt not in seen and len(path)<6:seen.add(nxt);queue.append((nxt,path+[r]))
    return None

def policy_for(connection,policy,grant):
    schema=source_schema(connection)
    authorized_orgs={o['sigla'] for o in grant['organizations']}
    unit=schema.removeprefix('moara_secp_').upper()
    if unit!='ATIVAS' and unit not in authorized_orgs:return {'objects':{}},{}
    baseline=allowed_objects(policy)
    fields={name.split('.',1)[1]:{f['name'] for f in item['fields']} for name,item in baseline.items() if name.startswith(schema+'.')}
    supports=set().union(*(scopes(grant,r) for r in HR))
    output=deepcopy(policy);output['objects']={};rules={}
    for name,item in baseline.items():
        if not name.startswith(schema+'.'):raise Rejected('Objetos de outra fonte no catálogo SECP')
        table=name.split('.',1)[1];ss=table_scopes(grant,table);fallback=False
        if not ss and table in DIMENSIONS:ss=supports;fallback=True
        kind=scope_kind(ss)
        if not kind:continue
        employee=path_to(table,'servidores',fields,grant['relations'])
        unit_path=path_to(table,'unidades_organizacionais',fields,grant['relations'])
        org_path=path_to(table,'orgaos',fields,grant['relations'])
        if kind!='organization' and employee is None and unit_path is None and table!='orgaos' and table not in {'cargos','categorias_pessoas'}:continue
        selected=deepcopy(item)
        if fallback:selected['fields']=[f for f in selected['fields'] if f['name'] in DIMENSIONS[table]]
        if fallback and kind=='organization' and table in {'servidores','usuarios','lotacoes'}:
            selected['support_only']=True
            selected['fields']=[f for f in selected['fields'] if f['name'] in {'id','usuario_id','orgao_id','servidor_id','unidade_id','ativo','status','data_inicio','data_fim'}]
        if not selected['fields']:continue
        output['objects'][name]=selected
        rules[name]={'kind':kind,'scopes':ss,'employee_path':employee,'unit_path':unit_path,'org_path':org_path}
    output['view_hashes']={k:v for k,v in policy.get('view_hashes',{}).items() if k in output['objects']}
    return output,rules

def descriptor(grant,policy,rules):
    kinds={r['kind'] for r in rules.values()}
    return {'profile':grant['profile'],'profile_id':grant['profile_id'],'scope':'organization' if 'organization' in kinds else ('team' if 'team' in kinds else 'own'),
        'organizations':[o['sigla'] for o in grant['organizations']],
        'fingerprint':hashlib.sha256((grant['fingerprint']+json.dumps(policy,sort_keys=True,default=str)).encode()).hexdigest()}

def scoped_sql(validated,connection,policy,grant,rules):
    """Every physical table becomes a filtered relation before joins/aggregates.

    IDs are DB-API parameters, never SQL text or instructions supplied by a model.
    Qualified CTE aliases cannot shadow physical schema.view references.
    """
    schema=source_schema(connection);tree=sqlglot.parse_one(validated,read='postgres');params={};used=set()
    def parameter(values):
        key='moara_scope_'+str(len(params));params[key]=sorted(set(values))
        return 'CAST(:'+key+' AS uuid[])'
    def predicate(base,path,values):
        array=parameter(values)
        if path==[]:return base+'.id = ANY('+array+')'
        if path is None:raise Rejected('A relação de escopo do SECP não foi verificada')
        first=path[0];alias='rbac_1';body='SELECT 1 FROM '+schema+'.'+first['target']+' '+alias
        used.add(schema+'.'+first['target'])
        condition=base+'."'+first['field']+'"='+alias+'."'+first['key']+'"'
        for index,edge in enumerate(path[1:],2):
            nxt='rbac_'+str(index)
            body+=' JOIN '+schema+'.'+edge['target']+' '+nxt+' ON '+alias+'."'+edge['field']+'"='+nxt+'."'+edge['key']+'"'
            used.add(schema+'.'+edge['target']);alias=nxt
        return 'EXISTS ('+body+' WHERE '+condition+' AND '+alias+'.id=ANY('+array+'))'
    for table in list(tree.find_all(exp.Table)):
        name=table.db+'.'+table.name
        if name not in policy['objects']:continue # A CTE reference, already checked by validate_sql.
        if name not in rules:raise Rejected('Seu perfil do SECP não autoriza esse objeto')
        rule=rules[name];base='rbac_base';conditions=[]
        if rule['org_path'] is not None:
            conditions.append(predicate(base,rule['org_path'],[o['id'] for o in grant['organizations']]))
        if rule['kind']!='organization':
            own=grant['vectors']['own'] if 'proprio' in rule['scopes'] else []
            team=grant['vectors']['team'] if rule['scopes'] & {'chefia','subordinados'} else []
            if rule['employee_path'] is not None:conditions.append(predicate(base,rule['employee_path'],own+team))
            elif rule['unit_path'] is not None:
                units=(grant['vectors']['own_units'] if 'proprio' in rule['scopes'] else [])+(grant['vectors']['team_units'] if rule['scopes'] & {'chefia','subordinados'} else [])
                conditions.append(predicate(base,rule['unit_path'],units))
            elif table.name not in {'orgaos','cargos','categorias_pessoas'}:raise Rejected('Objeto sem escopo funcional verificável')
        alias=table.alias or table.name
        relation=sqlglot.parse_one('SELECT '+base+'.* FROM '+name+' '+base+(' WHERE '+' AND '.join('('+c+')' for c in conditions) if conditions else ''),read='postgres')
        table.replace(relation.subquery(alias))
    keys=list(params)
    for placeholder in list(tree.find_all(exp.Placeholder)):
        if placeholder.this not in params:raise Rejected('Parâmetro de escopo desconhecido')
        placeholder.replace(exp.Var(this='$'+str(keys.index(placeholder.this)+1)))
    return tree.sql(dialect='postgres'),[params[k] for k in keys],sorted(used)
