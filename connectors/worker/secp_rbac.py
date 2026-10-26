"""Live SECP RBAC reads, using the bundled, unchanged SECP profile resolver.

This module is private to the PostgreSQL worker. Its metadata credential is a
separate mounted secret and is never a configurable Moara data source.
"""
import hashlib
import json
import os
import subprocess
from collections import deque
from pathlib import Path
from uuid import UUID
from common.policy import Rejected,IDENTIFIER,allowed_objects

META='moara_secp_rbac'
RELATIONS_SQL="""SELECT a.relname AS origin,x.attname AS field,b.relname AS target,y.attname AS key
    FROM pg_constraint c JOIN pg_class a ON a.oid=c.conrelid JOIN pg_namespace n ON n.oid=a.relnamespace
    JOIN pg_class b ON b.oid=c.confrelid JOIN pg_namespace nb ON nb.oid=b.relnamespace
    JOIN pg_attribute x ON x.attrelid=a.oid AND x.attnum=c.conkey[1]
    JOIN pg_attribute y ON y.attrelid=b.oid AND y.attnum=c.confkey[1]
    WHERE c.contype='f' AND n.nspname='public' AND nb.nspname='public' AND cardinality(c.conkey)=1"""
TABLES={
 'users':'id,matricula,tipo,ativo',
 'servers':'id,usuario_id,orgao_id,ativo',
 'profiles':'id,codigo,nome,ativo,administrativo,excecao,perfil_destino_excecao_id,orgao_id,global',
 'assignments':'usuario_id,perfil_id,orgao_id,ativo',
 'permissions':'id,codigo,recurso,acao,escopo',
 'profile_permissions':'perfil_id,permissao_id',
 'section_permissions':'perfil_id,permissao_id,orgao_id,permitida',
 'releases':'tipo,chave,liberada',
 'organizations':'id,sigla,nome,ativo',
 'units':'id,orgao_id,unidade_pai_id,ativo',
 'lots':'servidor_id,unidade_id,status',
 'managers':'servidor_id,unidade_id,ativo,data_inicio,data_fim',
 'substitutions':'id,unidade_id,titular_servidor_id,substituto_servidor_id,tipo,status,data_inicio,data_fim',
 'absences':'servidor_id,ativo,data_inicio,data_fim',
}
ORIGINS=dict(zip(TABLES,('usuarios','servidores','perfis','usuarios_perfis','permissoes','perfis_permissoes','perfis_permissoes_orgaos','rotinas_liberacoes','orgaos','unidades_organizacionais','lotacoes','gestores_unidades','substituicoes_funcao','afastamentos_sarh')))

def rows(db,statement,params=(),limit=100000):
    from worker.sql_driver import fetch
    columns,values=fetch(db,statement,params,max_rows=limit+1)
    if len(values)>limit:raise Rejected('O escopo SECP excede o limite seguro; reduza a consulta')
    return [dict(zip(columns,[str(v) if isinstance(v,UUID) else v for v in row])) for row in values]

def table(db,name,where='',params=()):
    if name not in TABLES:raise Rejected('Catálogo RBAC desconhecido')
    return rows(db,'SELECT '+TABLES[name]+' FROM '+META+'.'+name+(' WHERE '+where if where else ''),params)

def snapshot(db,identity):
    users=table(db,'users','lower(matricula)=lower(%s)',(identity['username'],))
    if len(users)!=1 or not users[0]['ativo']:raise Rejected('Conta não encontrada ou inativa no SECP')
    user=users[0];uid=user['id']
    organizations=table(db,'organizations');orgs={o['id']:o for o in organizations}
    profiles=table(db,'profiles');permissions=table(db,'permissions')
    base=table(db,'profile_permissions');exceptions=table(db,'section_permissions')
    pmap={p['id']:p for p in permissions}
    def profile(p):
        return {'id':p['id'],'codigo':p['codigo'],'nome':p['nome'],'ativo':p['ativo'],
            'administrativo':p['administrativo'],'excecao':p['excecao'],'global':p['global'],
            'perfilDestinoExcecaoId':p['perfil_destino_excecao_id'],'orgaoId':p['orgao_id'],'orgao':orgs.get(p['orgao_id']),
            'permissoes':[{'permissaoId':v['permissao_id'],'permissao':pmap[v['permissao_id']]} for v in base if v['perfil_id']==p['id']],
            'permissoesSeccionais':[{'orgaoId':v['orgao_id'],'permissaoId':v['permissao_id'],'permitida':v['permitida'],'permissao':pmap[v['permissao_id']]} for v in exceptions if v['perfil_id']==p['id']]}
    profiles={p['id']:profile(p) for p in profiles}
    def assignments(user_id):
        return [{'orgaoId':a['orgao_id'],'orgao':orgs.get(a['orgao_id']),'perfil':profiles[a['perfil_id']]} for a in table(db,'assignments','usuario_id=%s AND ativo',(user_id,)) if a['perfil_id'] in profiles]
    links=assignments(uid);own_servers=table(db,'servers','usuario_id=%s',(uid,))
    if len(own_servers)>1:raise Rejected('Vínculo funcional ambíguo no SECP')
    auth_orgs={r['orgao_id'] for r in own_servers}|{a['orgaoId'] or a['perfil']['orgaoId'] for a in links}
    if not any(o['sigla']==identity['organization'] and o['id'] in auth_orgs and o['ativo'] for o in organizations):
        raise Rejected('A unidade do login institucional não corresponde ao vínculo do SECP')
    # Dates match the SECP automatic substitution resolver (start of local day).
    substitutions=rows(db,f'''SELECT x.* FROM {META}.substitutions x
        JOIN {META}.servers s ON s.id=x.substituto_servidor_id
        JOIN {META}.servers t ON t.id=x.titular_servidor_id
        WHERE s.usuario_id=%s AND s.ativo AND t.ativo AND x.tipo='AUTOMATICA' AND x.status='ATIVA'
        AND x.data_inicio <= (now() AT TIME ZONE 'America/Manaus')::date
        AND (x.data_fim IS NULL OR x.data_fim >= (now() AT TIME ZONE 'America/Manaus')::date)
        AND EXISTS(SELECT 1 FROM {META}.absences a WHERE a.servidor_id=t.id AND a.ativo
          AND a.data_inicio <= (now() AT TIME ZONE 'America/Manaus')::date
          AND (a.data_fim IS NULL OR a.data_fim >= (now() AT TIME ZONE 'America/Manaus')::date))''',(uid,))
    inherited=[];base_units=set()
    for sub in substitutions:
        holder=table(db,'servers','id=%s',(sub['titular_servidor_id'],))[0]
        managers=table(db,'managers',"servidor_id=%s AND ativo AND data_inicio <= (now() AT TIME ZONE 'America/Manaus')::date AND (data_fim IS NULL OR data_fim >= (now() AT TIME ZONE 'America/Manaus')::date)",(holder['id'],))
        inherited.append({'unidadeId':sub['unidade_id'],'titularServidor':{'gestores':[{'unidadeId':g['unidade_id']} for g in managers], 'usuario':{'perfis':assignments(holder['usuario_id'])}}})
        if sub['unidade_id']:base_units.add(sub['unidade_id'])
        base_units.update(g['unidade_id'] for g in managers)
    # The ordinary hierarchy resolver uses a current instant, not start of day.
    managers=rows(db,f'''SELECT g.unidade_id FROM {META}.managers g JOIN {META}.servers s ON s.id=g.servidor_id
        WHERE s.usuario_id=%s AND s.ativo AND g.ativo AND g.data_inicio <= now()
        AND (g.data_fim IS NULL OR g.data_fim >= now())''',(uid,))
    base_units.update(g['unidade_id'] for g in managers)
    units=table(db,'units');frontier=set(base_units)
    for _ in range(len(units)+1):
        more={u['id'] for u in units if u['ativo'] and u['unidade_pai_id'] in frontier}-base_units
        if not more:break
        base_units.update(more);frontier=more
    else:raise Rejected('Hierarquia SECP inválida')
    own=[s['id'] for s in own_servers if s['ativo']]
    subordinate=rows(db,f'''SELECT DISTINCT s.id FROM {META}.servers s
        JOIN {META}.users u ON u.id=s.usuario_id JOIN {META}.lots l ON l.servidor_id=s.id
        WHERE s.ativo AND u.ativo AND l.status='ATIVO' AND l.unidade_id=ANY(%s::uuid[])''',(sorted(base_units),)) if base_units else []
    own_units=rows(db,f"SELECT DISTINCT unidade_id FROM {META}.lots WHERE servidor_id=ANY(%s::uuid[]) AND status='ATIVO'",(own,)) if own else []
    value={'username':identity['username'],'profile':identity.get('profile'),
        'user':{**user,'nome':'','email':None,'senhaHash':None,'preferenciasAcessibilidade':None,
            'servidor':{'orgaoId':own_servers[0]['orgao_id']} if own_servers else None,'perfis':links},
        'permissions':permissions,'organizations':organizations,'releases':table(db,'releases'),'substitutions':inherited}
    vectors={'own':own,'team':sorted({r['id'] for r in subordinate}), 'own_units':sorted({r['unidade_id'] for r in own_units}),'team_units':sorted(base_units)}
    return value,vectors

def evaluate(identity):
    from common.contracts import Connection
    from worker.sql_driver import connection,verify_privileges,view_fingerprint
    path=Path(os.getenv('SECP_RBAC_CONFIG','/run/secrets/secp_rbac_config'))
    if not path.is_file():raise Rejected('Autorização RBAC do SECP indisponível')
    config=json.loads(path.read_text());c=Connection.model_validate(config['connection']).model_dump()
    if identity.get('issuer') not in config.get('directory_pins',{}).get(identity['organization'],[]):
        raise Rejected('O diretório deste login não é uma origem institucional aprovada para o SECP')
    with connection('postgres',c,{'password':config['password']},()) as db:
        verify_privileges('postgres',db,c)
        definitions=rows(db,"SELECT c.relname,pg_get_viewdef(c.oid,true) AS definition FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind='v'",(META,))
        if {r['relname'] for r in definitions}!=set(TABLES) or any(view_fingerprint(r['definition'])!=config['view_hashes'].get(r['relname']) for r in definitions):
            raise Rejected('O catálogo RBAC do SECP foi alterado; revise a integração')
        data,vectors=snapshot(db,identity)
        bundle=Path('/app/connectors/secp_rbac/resolver.cjs')
        manifest=json.loads(bundle.with_name('manifest.json').read_text())
        if hashlib.sha256(bundle.read_bytes()).hexdigest()!=manifest['sha256']:raise Rejected('Versão da autorização SECP inválida')
        result=subprocess.run(['node','--max-old-space-size=128',str(bundle)],input=json.dumps(data,default=str),text=True,capture_output=True,timeout=5,env={'PATH':os.environ.get('PATH',''),'TZ':'America/Manaus','AUTH_SESSION_CACHE_TTL_SECONDS':'0'})
        if result.returncode or len(result.stdout)>2*1024**2:raise Rejected('Perfil do SECP não atribuído ou sem autorização')
        grant=json.loads(result.stdout);grant['vectors']=vectors;grant['version']=manifest['sha256']
        grant['permissions']=sorted(grant['permissions']);grant['organizations']=sorted(grant['organizations'],key=lambda o:o['id'])
        relations=rows(db,RELATIONS_SQL)
        ordered=lambda values:sorted(values,key=lambda r:(r['origin'],r['field'],r['target'],r['key']))
        if ordered(relations)!=ordered(config.get('relations',[])):raise Rejected('Os relacionamentos do SECP mudaram; revise os filtros RBAC antes de consultar os dados')
    grant['relations']=relations
    grant['fingerprint']=hashlib.sha256(json.dumps({k:v for k,v in grant.items() if k not in {'profiles','relations'}},sort_keys=True).encode()).hexdigest()
    return grant
