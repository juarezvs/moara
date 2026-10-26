"""SECP business catalog and tenant-safe view definitions, without application secrets."""
import re
from collections import deque
from uuid import UUID

TABLES=set('''orgaos unidades_organizacionais cargos servidores usuarios categorias_pessoas lotacoes
dispensas_ponto_servidores afastamentos_sarh programacoes_ferias gestores_unidades funcoes_confianca_referencias
substituicoes_funcao pagamentos_substituicoes_funcao pagamentos_substituicoes_funcao_dias
jornadas jornadas_dias jornadas_faixas_horarios escalas escalas_dias jornadas_servidores
marcacoes apuracoes_diarias processamentos_espelho_ponto ocorrencias_frequencia
banco_horas_saldos banco_horas_movimentos banco_horas_autorizacoes solicitacoes solicitacoes_eventos
fechamentos_mensais_unidades homologacoes_servidores_meses boletins_frequencia boletins_frequencia_servidores
calendarios_institucionais tipos_feriados_suspensoes estados cidades fusos_horarios regulamentacoes_ponto_orgaos
procedimentos_administrativos_frequencia procedimentos_administrativos_frequencia_execucoes
acompanhamentos_estagio_mensais acompanhamentos_estagio_dias estagios_supervisoes
recessos_forenses recessos_convocacoes recessos_convocados recessos_espelhos recessos_homologacoes
overtime_campaigns overtime_campaign_accounts overtime_budget_operations overtime_budget_movements
overtime_policies overtime_policy_versions overtime_rate_rules overtime_workflow_definitions
overtime_workflow_versions overtime_workflow_step_definitions overtime_workflow_transitions
overtime_responsibility_assignments overtime_requests overtime_request_days overtime_request_history
overtime_budget_reviews overtime_final_decisions overtime_authorizations overtime_authorization_days
overtime_payroll_batches overtime_payroll_batch_employees overtime_payroll_batch_lines
autorizacoes_horas_extras autorizacoes_horas_extras_servidores autorizacoes_horas_extras_regras
horas_extras_execucoes_intervalos horas_extras_classificacoes_intervalos horas_extras_atestos
horas_extras_calculos horas_extras_calculos_itens horas_extras_eventos
mct_politicas_versoes mct_configuracoes_apuracao mct_rubricas_versoes mct_naturezas_rubricas
mct_regras_versoes mct_regras_efeitos mct_execucoes mct_comparacoes_legado mct_eventos_entrada
mct_segmentos mct_fatos_conformidade mct_rubricas_aplicadas overtime_projects overtime_project_versions
overtime_project_items overtime_project_events overtime_project_fundings overtime_extraordinary_credits
overtime_extraordinary_credit_uses'''.split())
GLOBAL={'cargos','categorias_pessoas','funcoes_confianca_referencias','tipos_feriados_suspensoes','estados','cidades','fusos_horarios','mct_naturezas_rubricas'}
SHARED_NULL={'jornadas','escalas','calendarios_institucionais','overtime_policies','overtime_workflow_definitions'}
PRIVATE=re.compile(r'cpf|(^|_)pis($|_)|senha|password|secret|token|chave|cipher|salt|hash|biometr|face|template|latitude|longitude|geometr|(^|_)ip$|user_agent|nascimento|endereco|telefone|email|salari|remunera|conta_banc|diagnost|(^|_)cid($|_)|observa|justific|payload|metadad|configurac|^dados_|retorno|erro|parecer|motivo|anexo|arquivo|caminho|url|processo|documento|mensagem|comentario|foto|imagem|trace|stack',re.I)
IDENT=re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,62}$')

def quote(value):
    if not IDENT.fullmatch(value):raise ValueError('Invalid catalog identifier')
    return '"'+value+'"'

def public_columns(table,columns):
    result=[]
    for item in columns:
        name=item['column_name']
        if not IDENT.fullmatch(name) or PRIVATE.search(name) or item['data_type'] in {'json','jsonb','bytea','ARRAY'}:continue
        if table=='usuarios' and name not in {'id','matricula','nome','tipo','ativo'}:continue
        if table=='afastamentos_sarh' and name in {'tipo_afastamento_id','tipo_codigo','tipo_descricao'}:continue
        if name in {'descricao','titulo'} and table not in GLOBAL|SHARED_NULL|{'orgaos','unidades_organizacionais','regulamentacoes_ponto_orgaos'}:continue
        result.append(item)
    return result

def scope_path(table,relations):
    if table=='orgaos':return []
    queue=deque([(table,[])]);seen={table}
    while queue:
        current,path=queue.popleft()
        edges=sorted((r for r in relations if r['table_name']==current),key=lambda r:(r['target_table']!='orgaos',r['target_table']!='unidades_organizacionais',r['column_name']))
        for edge in edges:
            target=edge['target_table']
            if target not in TABLES or target=='usuarios':continue
            if target=='orgaos':return path+[edge]
            if target not in seen and len(path)<5:seen.add(target);queue.append((target,path+[edge]))
    return None

def definitions(catalog,organization):
    organizations=organization if isinstance(organization,list) else [organization]
    if not 1<=len(organizations)<=20:raise ValueError('Invalid organization scope')
    literals=["'"+str(UUID(value))+"'" for value in sorted(set(organizations))]
    # PostgreSQL deparses IN lists into ANY(ARRAY); use a plain Boolean scope
    # so the immutable view stays within the same bounded SELECT grammar.
    def scoped(column):return '('+' OR '.join(column+'='+value for value in literals)+')'
    by_table={}
    for c in catalog['columns']:
        if c['table_schema']=='public' and c['table_name'] in TABLES:by_table.setdefault(c['table_name'],[]).append(c)
    results={};skipped={}
    for table,columns in by_table.items():
        fields=public_columns(table,columns)
        if not fields:skipped[table]='no_public_columns';continue
        path=scope_path(table,catalog['relations'])
        base='public.'+quote(table)+' t';joins=[]
        if table=='usuarios':
            joins=['JOIN public.servidores s1 ON s1.usuario_id=t.id'];condition=scoped('s1.orgao_id')
        elif table=='orgaos':condition=scoped('t.id')
        elif path:
            previous='t'
            for i,edge in enumerate(path,1):
                alias='s'+str(i);joins.append('JOIN public.'+quote(edge['target_table'])+' '+alias+' ON '+previous+'.'+quote(edge['column_name'])+'='+alias+'.'+quote(edge['target_column']));previous=alias
            condition=scoped(previous+'.id')
            if table in SHARED_NULL|GLOBAL and len(path)==1:
                # Global definitions are visible too; avoid the inner join
                # dropping them before the nullable organization condition.
                joins=[];condition='(t.'+quote(path[0]['column_name'])+' IS NULL OR '+scoped('t.'+quote(path[0]['column_name']))+')'
        elif table in GLOBAL:condition='TRUE'
        else:skipped[table]='no_verified_organization_path';continue
        projection=[]
        for f in fields:
            col=quote(f['column_name']);value='t.'+col
            if f['data_type']=='USER-DEFINED':value='CAST('+value+' AS text)'
            projection.append(value+' AS '+col)
        query='SELECT '+('DISTINCT ' if table=='usuarios' else '')+', '.join(projection)+' FROM '+base+' '+' '.join(joins)+' WHERE '+condition
        results[table]={'query':query,'columns':[f['column_name'] for f in fields]}
    if not {'orgaos','servidores','unidades_organizacionais','lotacoes'}<=results.keys():raise ValueError('Core SECP relations are missing')
    return results,skipped
