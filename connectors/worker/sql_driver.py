"""Isolated DB-API adapters. Fixed metadata queries never accept user SQL fragments."""
import contextlib
import os
import hashlib
import hmac
from pathlib import Path
from common.policy import Rejected, IDENTIFIER, pinned_ip, validate_sql, safe_rows, NODES
import sqlglot
from sqlglot import exp

SYSTEM = {'pg_catalog', 'information_schema', 'sys', 'system', 'mysql', 'performance_schema', 'dbo_system', 'ctxsys', 'xdb', 'mdsys', 'sysaux', 'outln', 'dbsnmp', 'ords_metadata', 'appqossys', 'audsys', 'wmsys', 'dvsys', 'lbacs﻿ys'}

@contextlib.contextmanager
def connection(kind, c, credential, forbidden):
    ip = pinned_ip(c, forbidden) if kind != 'sqlite' else None
    password = credential.get('password', '')
    if any(x in c['database'] + c['username'] for x in [';', '\r', '\n', '\x00']): raise Rejected('Identificação de conexão inválida')
    ca = '/tmp/ca-' + str(os.getpid()) + '.pem'
    if c.get('ca_pem'):
        Path(ca).write_text(c['ca_pem']); os.chmod(ca, 0o600)
    db = None
    try:
        timeout = c['timeout']
        if kind == 'postgres':
            import psycopg
            db = psycopg.connect(host=c['host'], hostaddr=ip, port=c['port'], dbname=c['database'],
                user=c['username'], password=password, connect_timeout=timeout,
                sslmode='verify-full' if c['tls'] else 'disable',
                **({'sslrootcert': ca} if c.get('ca_pem') else {}))
            # psycopg starts its transaction before the first execute. Apply
            # the mode to that transaction rather than issuing nested BEGIN.
            db.execute('SET TRANSACTION READ ONLY')
            if db.execute('SHOW transaction_read_only').fetchone()[0]!='on':raise Rejected('A transação PostgreSQL não está em modo somente leitura')
            db.execute("SELECT set_config('statement_timeout', %s, true)", (str(timeout * 1000),))
            db.execute("SELECT set_config('lock_timeout', '2000', true)")
            db.execute("SET LOCAL search_path = pg_catalog")
        elif kind == 'mysql':
            import pymysql, ssl, socket
            # Preconnected pinned socket; original host remains the TLS verification name.
            db = pymysql.connect(host=c['host'], port=c['port'], user=c['username'], password=password,
                database=c['database'], connect_timeout=timeout, read_timeout=timeout, write_timeout=timeout,
                autocommit=False, defer_connect=True,
                ssl_ca=ca if c.get('ca_pem') else None, ssl_verify_cert=c['tls'], ssl_verify_identity=c['tls'],
                ssl=ssl.create_default_context(cafile=ca if c.get('ca_pem') else None) if c['tls'] else None)
            sock = socket.create_connection((ip, c['port']), timeout=timeout)
            db.connect(sock=sock)
            with db.cursor() as cur:
                try: cur.execute('SET SESSION MAX_EXECUTION_TIME = ' + str(timeout * 1000))
                except pymysql.err.OperationalError: cur.execute('SET SESSION max_statement_time = ' + str(timeout))
                cur.execute('START TRANSACTION READ ONLY')
        elif kind == 'mssql':
            import pyodbc
            def quoted(s): return '{' + str(s).replace('}', '}}') + '}'
            parts = {'DRIVER': 'ODBC Driver 18 for SQL Server', 'SERVER': 'tcp:' + ip + ',' + str(c['port']),
                'DATABASE': c['database'], 'UID': c['username'], 'PWD': password,
                'Encrypt': 'yes' if c['tls'] else 'no', 'TrustServerCertificate': 'no' if c['tls'] else 'yes',
                'HostNameInCertificate': c['host'], 'APP': 'Curumim-Readonly-Connector'}
            if c.get('ca_pem'): raise Rejected('SQL Server usa a cadeia de confiança do sistema; CA personalizada indisponível nesta versão')
            db = pyodbc.connect(';'.join(k + '=' + quoted(v) for k, v in parts.items()), timeout=timeout, autocommit=False)
            db.timeout = timeout
            db.cursor().execute('SET LOCK_TIMEOUT 2000')
        elif kind == 'oracle':
            import oracledb, ssl
            role = c.get('oracle_role', '')
            schema = c.get('oracle_schema', '')
            if any(value and not IDENTIFIER.fullmatch(value) for value in (role, schema)):
                raise Rejected('Role ou schema Oracle inválido')
            if c.get('oracle_readonly_mode') == 'transaction' and (not role or not schema):
                raise Rejected('O modo Oracle institucional exige role e schema explícitos')
            # Legacy SARH password verifiers require OCI. Each request has its
            # own spawned process; TCPS continues through the verified thin path.
            if os.getenv('ORACLE_CLIENT_MODE')=='thick' and not c['tls']:
                oracledb.init_oracle_client()
            params = oracledb.ConnectParams(host=ip, port=c['port'], service_name=c['database'],
                protocol='tcps' if c['tls'] else 'tcp', tcp_connect_timeout=timeout,
                ssl_server_dn_match=c['tls'], ssl_server_cert_dn=None,
                ssl_context=ssl.create_default_context(cafile=ca if c.get('ca_pem') else None) if c['tls'] else None)
            if c['tls'] and c['host'] != ip:
                raise Rejected('Oracle TCPS exige certificado válido para o IP aprovado nesta versão')
            db = oracledb.connect(user=c['username'], password=password, params=params)
            db.call_timeout = timeout * 1000
            # Drop unrelated application/administrative roles before opening the
            # read-only snapshot. The role name is a validated identifier.
            if role:
                db.cursor().execute('SET ROLE "' + role.upper() + '"')
            db.cursor().execute('SET TRANSACTION READ ONLY')
        elif kind == 'sqlite':
            import sqlite3, time
            path = Path('/data/sqlite') / (c['sqlite_id'] + '.db')
            if not c['sqlite_id'] or not path.is_file(): raise Rejected('Importe uma cópia SQLite primeiro')
            db = sqlite3.connect('file:' + str(path) + '?mode=ro&immutable=1', uri=True, timeout=timeout)
            db.execute('PRAGMA query_only=ON')
            db.execute('PRAGMA trusted_schema=OFF');db.enable_load_extension(False)
            deadline = time.monotonic() + timeout
            db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            safe_functions = {'count', 'sum', 'avg', 'min', 'max', 'lower', 'upper', 'length', 'abs', 'round', 'coalesce', 'like', 'ifnull'}
            deny = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE, sqlite3.SQLITE_ATTACH,
                sqlite3.SQLITE_DETACH, sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_CREATE_TABLE,
                sqlite3.SQLITE_PRAGMA, sqlite3.SQLITE_CREATE_VTABLE, sqlite3.SQLITE_DROP_VTABLE}
            db.set_authorizer(lambda action, arg1, arg2, database, trigger:
                sqlite3.SQLITE_OK if action==sqlite3.SQLITE_PRAGMA and arg1=='table_xinfo' and arg2 and IDENTIFIER.fullmatch(arg2) else
                sqlite3.SQLITE_DENY if action in deny or (action == sqlite3.SQLITE_FUNCTION and (arg2 or '').lower() not in safe_functions)
                else sqlite3.SQLITE_OK)
        else: raise Rejected('Driver indisponível')
        yield db
    finally:
        if db:
            try: db.rollback()
            except Exception: pass
            db.close()
        Path(ca).unlink(missing_ok=True)

def fetch(db, sql, params=(), max_rows=5000):
    cur = db.cursor()
    try:
        if params:cur.execute(sql, params)
        else:cur.execute(sql)
        columns = [v[0] for v in cur.description] if cur.description else []
        return columns, cur.fetchmany(max_rows) if cur.description else []
    finally: cur.close()

def verify_privileges(kind, db, c=None):
    if kind == 'postgres':
        _, roles = fetch(db, 'SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user')
        if not roles or any(roles[0]): raise Rejected('Credencial administrativa não permitida')
        _, dangerous = fetch(db, "SELECT rolname FROM pg_roles WHERE rolname IN ('pg_write_all_data','pg_execute_server_program','pg_read_server_files','pg_write_server_files') AND pg_has_role(oid,'USAGE')")
        _, writes = fetch(db, """SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%'
            AND c.relkind IN ('r','v','m','f','p') AND (has_table_privilege(c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES')
            OR has_any_column_privilege(c.oid,'INSERT,UPDATE,REFERENCES')) LIMIT 1""")
        _, creates = fetch(db, "SELECT oid FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname<>'information_schema' AND has_schema_privilege(oid,'CREATE') LIMIT 1")
        _, database_create=fetch(db,"SELECT has_database_privilege(current_database(),'CREATE')")
        _, funcs = fetch(db, """SELECT p.oid FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND has_function_privilege(p.oid,'EXECUTE') LIMIT 1""")
        pinned=bool(c and c.get('postgres_readonly_mode')=='pinned_views')
        if dangerous or writes or creates or (funcs and not pinned) or database_create[0][0]: raise Rejected('Credencial deve ter apenas leitura, sem CREATE, escrita ou EXECUTE de rotinas de aplicação')
        if pinned:
            return {'readonly_verified':True,'credential_readonly':not bool(funcs),
                'verification':'readonly_transaction_pinned_views','public_routines_callable_outside_connector':bool(funcs)}
    elif kind == 'mysql':
        _, grants = fetch(db, 'SHOW GRANTS')
        import re
        for row in grants:
            match = re.match(r'^GRANT (.+?) ON ', row[0], flags=re.I)
            if not match or any(p.strip().upper() not in {'SELECT', 'SHOW VIEW', 'USAGE'} for p in match[1].split(',')) or 'WITH GRANT OPTION' in row[0].upper():
                raise Rejected('Use grants diretos SELECT/SHOW VIEW; escrita, EXECUTE, roles e privilégios administrativos são recusados')
    elif kind == 'mssql':
        _, server_permissions=fetch(db,"SELECT permission_name FROM sys.fn_my_permissions(NULL,'SERVER')")
        safe_server={'CONNECT SQL','VIEW ANY DATABASE','VIEW ANY COLUMN ENCRYPTION KEY DEFINITION','VIEW ANY COLUMN MASTER KEY DEFINITION'}
        if any(row[0] not in safe_server for row in server_permissions):raise Rejected('Credencial SQL Server possui privilégios administrativos no servidor')
        _, permissions = fetch(db, "SELECT permission_name FROM sys.fn_my_permissions(NULL,'DATABASE')")
        if any(row[0] not in {'CONNECT', 'SELECT', 'VIEW DEFINITION', 'VIEW DATABASE STATE','VIEW SECURITY DEFINITION','VIEW PERFORMANCE DEFINITION','VIEW ANY COLUMN ENCRYPTION KEY DEFINITION','VIEW ANY COLUMN MASTER KEY DEFINITION'} for row in permissions):
            raise Rejected('Credencial SQL Server possui privilégios além de leitura')
        _, server = fetch(db, "SELECT IS_SRVROLEMEMBER('sysadmin'),IS_SRVROLEMEMBER('securityadmin'),IS_MEMBER('db_owner'),IS_MEMBER('db_datawriter')")
        _, dangerous = fetch(db, """SELECT TOP (1) o.object_id FROM sys.objects o WHERE o.is_ms_shipped=0 AND (
            HAS_PERMS_BY_NAME(QUOTENAME(SCHEMA_NAME(o.schema_id))+'.'+QUOTENAME(o.name),'OBJECT','INSERT')=1 OR
            HAS_PERMS_BY_NAME(QUOTENAME(SCHEMA_NAME(o.schema_id))+'.'+QUOTENAME(o.name),'OBJECT','UPDATE')=1 OR
            HAS_PERMS_BY_NAME(QUOTENAME(SCHEMA_NAME(o.schema_id))+'.'+QUOTENAME(o.name),'OBJECT','DELETE')=1 OR
            HAS_PERMS_BY_NAME(QUOTENAME(SCHEMA_NAME(o.schema_id))+'.'+QUOTENAME(o.name),'OBJECT','EXECUTE')=1 OR
            HAS_PERMS_BY_NAME(QUOTENAME(SCHEMA_NAME(o.schema_id))+'.'+QUOTENAME(o.name),'OBJECT','ALTER')=1)""")
        if any(v for v in server[0]) or dangerous: raise Rejected('Credencial SQL Server possui escrita ou execução de rotinas')
    elif kind == 'oracle':
        _, privileges = fetch(db, 'SELECT privilege FROM session_privs')
        if c and c.get('oracle_readonly_mode') == 'transaction':
            # Institutional SARH roles also grant application DML. They are
            # confined here by SET TRANSACTION READ ONLY, the bounded SELECT
            # parser, live view validation and rollback on every exit. This
            # never claims that the shared credential itself is read-only.
            if any(p[0] not in {'CREATE SESSION', 'ALTER SESSION'} for p in privileges):
                raise Rejected('A role Oracle selecionada ainda possui privilégios administrativos; use uma role SARH restrita')
            return {'readonly_verified': True, 'credential_readonly': False,
                'verification': 'oracle_readonly_transaction', 'restricted_role': c['oracle_role'].upper()}
        _, owned = fetch(db, 'SELECT object_name FROM user_objects WHERE ROWNUM<=1')
        _, object_writes = fetch(db, """SELECT p.table_schema,p.table_name FROM all_tab_privs p JOIN all_objects o
            ON o.owner=p.table_schema AND o.object_name=p.table_name WHERE o.oracle_maintained='N'
            AND p.privilege NOT IN ('SELECT','READ') AND (p.grantee IN (USER,'PUBLIC') OR p.grantee IN (SELECT role FROM session_roles)) AND ROWNUM<=1""")
        _, column_writes=fetch(db,"SELECT table_schema,table_name FROM all_col_privs WHERE privilege<>'SELECT' AND (grantee IN (USER,'PUBLIC') OR grantee IN (SELECT role FROM session_roles)) AND ROWNUM<=1")
        if any(p[0] not in {'CREATE SESSION'} for p in privileges) or owned or object_writes or column_writes:
            raise Rejected('Oracle exige usuário sem objetos próprios e apenas CREATE SESSION + SELECT nos objetos autorizados')
    elif kind != 'sqlite': raise Rejected('Verificação de privilégios indisponível')
    return {'readonly_verified': True, 'verification': 'effective_privileges' if kind != 'sqlite' else 'immutable_snapshot_authorizer'}

def discover(kind, db, c):
    if kind == 'postgres':
        sql = """SELECT n.nspname,c.relname,c.relkind,a.attname,format_type(a.atttypid,a.atttypmod),
            CASE WHEN c.relkind='v' THEN pg_get_viewdef(c.oid,true) ELSE '' END
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid
            WHERE c.relkind IN ('r','p','v','m') AND a.attnum>0 AND NOT a.attisdropped
            AND n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema'
            AND has_column_privilege(c.oid,a.attname,'SELECT') ORDER BY 1,2,a.attnum"""
    elif kind == 'mysql':
        sql = """SELECT c.TABLE_SCHEMA,c.TABLE_NAME,t.TABLE_TYPE,c.COLUMN_NAME,c.DATA_TYPE,COALESCE(v.VIEW_DEFINITION,'')
            FROM information_schema.COLUMNS c JOIN information_schema.TABLES t ON t.TABLE_SCHEMA=c.TABLE_SCHEMA AND t.TABLE_NAME=c.TABLE_NAME
            LEFT JOIN information_schema.VIEWS v ON v.TABLE_SCHEMA=c.TABLE_SCHEMA AND v.TABLE_NAME=c.TABLE_NAME
            WHERE c.TABLE_SCHEMA=DATABASE() ORDER BY c.TABLE_SCHEMA,c.TABLE_NAME,c.ORDINAL_POSITION"""
    elif kind == 'mssql':
        sql = """SELECT c.TABLE_SCHEMA,c.TABLE_NAME,t.TABLE_TYPE,c.COLUMN_NAME,c.DATA_TYPE,COALESCE(v.VIEW_DEFINITION,'')
            FROM INFORMATION_SCHEMA.COLUMNS c JOIN INFORMATION_SCHEMA.TABLES t ON t.TABLE_SCHEMA=c.TABLE_SCHEMA AND t.TABLE_NAME=c.TABLE_NAME
            LEFT JOIN INFORMATION_SCHEMA.VIEWS v ON v.TABLE_SCHEMA=c.TABLE_SCHEMA AND v.TABLE_NAME=c.TABLE_NAME
            WHERE c.TABLE_SCHEMA NOT IN ('sys','INFORMATION_SCHEMA') ORDER BY c.TABLE_SCHEMA,c.TABLE_NAME,c.ORDINAL_POSITION"""
    elif kind == 'oracle':
        sql = """SELECT c.OWNER,c.TABLE_NAME,CASE WHEN v.VIEW_NAME IS NOT NULL THEN 'VIEW' ELSE 'TABLE' END,
            c.COLUMN_NAME,c.DATA_TYPE,'' FROM ALL_TAB_COLUMNS c LEFT JOIN ALL_VIEWS v ON v.OWNER=c.OWNER AND v.VIEW_NAME=c.TABLE_NAME
            WHERE c.OWNER NOT IN ('SYS','SYSTEM','XDB','CTXSYS','MDSYS','OUTLN','DBSNMP','AUDSYS','ORDS_METADATA','ORDDATA','WMSYS')
            ORDER BY c.OWNER,c.TABLE_NAME,c.COLUMN_ID"""
        if c.get('oracle_schema'):
            sql = sql.replace('ORDER BY c.OWNER', 'AND c.OWNER=:1 ORDER BY c.OWNER')
    elif kind == 'sqlite':
        _, tables = fetch(db, "SELECT name,type,sql FROM main.sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name")
        catalog = {}
        for name, typ, definition in tables:
            if not IDENTIFIER.fullmatch(name): continue
            # No PRAGMA supplied by clients; use table-valued metadata before authorizer restrictions.
            _, rows = fetch(db, 'PRAGMA main.table_xinfo("'+name+'")')
            fields=[{'name':row[1],'type':row[2] or 'unknown','sensitive':bool(__import__('re').search(r'password|senha|secret|token|cpf|email|salario',row[1],__import__('re').I))} for row in rows if row[6]!=1 and IDENTIFIER.fullmatch(row[1])]
            catalog['main.' + name] = {'type': typ, 'fields': fields,
                'definition': definition if typ == 'view' else ''}
        return {'database': c['database'] or 'snapshot', 'objects': catalog, 'relationships': []}
    params = (c['oracle_schema'].upper(),) if kind == 'oracle' and c.get('oracle_schema') else ()
    _, rows = fetch(db, sql, params, max_rows=50000 if params else 5000)
    catalog = {}
    for schema, name, typ, col, dtype, definition in rows:
        if schema.lower() in SYSTEM or not all(IDENTIFIER.fullmatch(x) for x in [schema, name, col]): continue
        key = schema + '.' + name
        item = catalog.setdefault(key, {'type': 'view' if str(typ).lower() in {'view','v'} else 'table', 'fields': [], 'definition': str(definition or '')[:30000]})
        item['fields'].append({'name': col, 'type': dtype, 'sensitive': bool(__import__('re').search(r'password|senha|secret|token|cpf|email|salario', col, __import__('re').I))})
    if kind == 'oracle':
        for key, item in catalog.items():
            if item['type'] == 'view':
                owner, name = key.split('.')
                _, definition = fetch(db, 'SELECT text FROM all_views WHERE owner=:1 AND view_name=:2', (owner, name), 1)
                item['definition'] = str(definition[0][0])[:30000] if definition else ''
    relationships = []
    if kind == 'oracle':
        # Two bounded dictionary reads avoid costly joins between Oracle's
        # ALL_* views. Pair composite keys by constraint and ordinal in memory.
        params=(c['oracle_schema'].upper(),) if c.get('oracle_schema') else ()
        predicate=' AND OWNER=:1' if params else ''
        _, constraints=fetch(db,"SELECT OWNER,CONSTRAINT_NAME,TABLE_NAME,CONSTRAINT_TYPE,R_OWNER,R_CONSTRAINT_NAME,STATUS,VALIDATED FROM ALL_CONSTRAINTS WHERE CONSTRAINT_TYPE IN ('P','U','R')"+predicate,params,max_rows=50001)
        _, columns=fetch(db,'SELECT OWNER,CONSTRAINT_NAME,TABLE_NAME,COLUMN_NAME,POSITION FROM ALL_CONS_COLUMNS WHERE 1=1'+predicate,params,max_rows=50001)
        if len(constraints)>50000 or len(columns)>50000:raise Rejected('Cat?logo de chaves Oracle excede o limite seguro')
        definitions={(owner,name):(table,kind,r_owner,r_name,status,validated) for owner,name,table,kind,r_owner,r_name,status,validated in constraints}
        pairs={}
        for owner,name,table,column,position in columns:pairs.setdefault((owner,name),[]).append((position,column))
        for (owner,name),(table,typ,r_owner,r_name,status,validated) in definitions.items():
            if status!='ENABLED' or validated!='VALIDATED':continue
            origin=owner+'.'+table
            if origin not in catalog:continue
            source=sorted(pairs.get((owner,name),[]))
            if not source:continue
            visible={f['name'] for f in catalog[origin]['fields']}
            if any(column not in visible for _,column in source):continue
            if typ=='P':catalog[origin]['primary_key']=[column for _,column in source]
            if typ!='R':continue
            target_def=definitions.get((r_owner,r_name))
            if not target_def or target_def[4]!='ENABLED' or target_def[5]!='VALIDATED':continue
            target=r_owner+'.'+target_def[0]
            if target not in catalog:continue
            referenced=dict(pairs.get((r_owner,r_name),[]))
            target_fields={f['name'] for f in catalog[target]['fields']}
            if len(referenced)!=len(source) or any(position not in referenced or referenced[position] not in target_fields for position,_ in source):continue
            relationships.extend({'from_object':origin,'from_field':column,'to_object':target,'to_field':referenced[position],
                'constraint_name':name,'position':position,'column_count':len(source)} for position,column in source)
    if kind in {'postgres', 'mysql', 'mssql'}:
        sql = """SELECT tc.table_schema,tc.table_name,kcu.column_name,ccu.table_schema,ccu.table_name,ccu.column_name
            FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name=kcu.constraint_name AND tc.constraint_schema=kcu.constraint_schema
            JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name=tc.constraint_name AND ccu.constraint_schema=tc.constraint_schema
            WHERE tc.constraint_type='FOREIGN KEY'""" if kind != 'mysql' else """SELECT TABLE_SCHEMA,TABLE_NAME,COLUMN_NAME,REFERENCED_TABLE_SCHEMA,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE WHERE REFERENCED_TABLE_NAME IS NOT NULL AND TABLE_SCHEMA=DATABASE()"""
        _, keys = fetch(db, sql)
        relationships = [{'from_object': a+'.'+b, 'from_field': col, 'to_object': d+'.'+e, 'to_field': target}
            for a,b,col,d,e,target in keys if a+'.'+b in catalog and d+'.'+e in catalog]
    return {'database': c['database'], 'objects': catalog, 'relationships': relationships}

def view_fingerprint(definition):
    return hashlib.sha256(definition.strip().replace('\r\n','\n').encode()).hexdigest()

def check_views(kind, objects, used, view_hashes=None):
    visited = set()
    def check(name):
        if name in visited: raise Rejected('Dependência circular de view')
        item = objects.get(name)
        if not item: raise Rejected('Dependência da view fora da política')
        if item.get('type') != 'view': return
        visited.add(name)
        definition = item.get('definition', '')
        if not definition: raise Rejected('Definição da view indisponível para validação')
        pinned=kind=='postgres' and view_hashes is not None
        if pinned and not hmac.compare_digest(view_fingerprint(definition),view_hashes.get(name,'')):
            raise Rejected('A definição da view foi alterada; é necessária nova aprovação')
        try:
            tree = sqlglot.parse_one(definition, read={'mssql':'tsql'}.get(kind,kind))
            if isinstance(tree, exp.Create) and kind == 'sqlite': tree = tree.expression
            if not isinstance(tree, exp.Select) or any(type(n).__name__ not in NODES for n in tree.walk()): raise ValueError()
            # A pinned, administrator-reviewed view can encapsulate base tables
            # unavailable to the connector role. Its definition is re-read and
            # checked on every query; the login cannot modify it or query bases.
            if pinned:
                if any(not table.db or table.catalog for table in tree.find_all(exp.Table)):raise ValueError()
                visited.remove(name)
                return
            for table in tree.find_all(exp.Table):
                if table.catalog: raise ValueError()
                if table.db: target = table.db+'.'+table.name
                else: target = name.split('.')[0]+'.'+table.name
                check(target)
        except Rejected: raise
        except Exception: raise Rejected('View contém construções ou funções não suportadas') from None
        visited.remove(name)
    for name in used: check(name)

def run(kind, body, forbidden):
    c, policy, request = body['connection'], body['policy'], body['request']
    secp=kind=='postgres' and c.get('postgres_readonly_mode')=='pinned_views' and body['method'] in {'authorize_secp','execute_readonly_query','preview_data'}
    grant=None;effective=policy;scope_rules={};access=None
    if secp:
        if not body.get('identity'):raise Rejected('O SECP exige identidade institucional verificada; o papel administrativo da Moara não substitui o RBAC do SECP')
        from worker.secp_rbac import evaluate
        from worker.secp_scope import policy_for,descriptor,scoped_sql
        grant=evaluate(body['identity']);effective,scope_rules=policy_for(c,policy,grant)
        access=descriptor(grant,effective,scope_rules)
        if body['method']=='authorize_secp':
            return {'objects':{n:{'fields':[f['name'] for f in v['fields']],'support_only':bool(v.get('support_only'))} for n,v in effective['objects'].items()},
                'access':access,'profiles':grant['profiles']}
        if not effective['objects']:raise Rejected('Seu perfil ativo do SECP não autoriza dados desta seccional')
    with connection(kind, c, body['credential'], forbidden) as db:
        privileges = verify_privileges(kind, db, c)
        if body['method'] == 'test_connection': return {**privileges, 'ok': True}
        catalog = discover(kind, db, c)
        if body['method'] == 'discover_catalog': return {**catalog, **privileges}
        if body['method'] == 'list_schemas': return {'schemas': sorted({x.split('.')[0] for x in catalog['objects']})}
        if body['method'] == 'list_objects': return {'objects': catalog['objects']}
        if body['method'] == 'describe_object':
            if request['object'] not in catalog['objects']: raise Rejected('Objeto indisponível')
            return catalog['objects'][request['object']]
        # Refresh view definitions/column existence on every execution; no stale policy bypass.
        for name, item in policy['objects'].items():
            if name not in catalog['objects']: raise Rejected('Estrutura alterada; execute descoberta novamente')
            existing = {f['name'] for f in catalog['objects'][name]['fields']}
            if any(f['name'] not in existing for f in item.get('fields', [])): raise Rejected('Campo removido; execute descoberta novamente')
            item['type'] = catalog['objects'][name]['type']; item['definition'] = catalog['objects'][name].get('definition','')
        raw = request['query']
        if body['method'] == 'preview_data':
            if request['object'] not in policy['objects']: raise Rejected('Objeto não autorizado')
            raw = 'SELECT * FROM ' + request['object']
        validated, used = validate_sql(kind, raw, effective)
        if secp:
            from common.secp_joins import validate_support_joins
            validate_support_joins(validated,effective,grant['relations'])
        pinned=kind=='postgres' and c.get('postgres_readonly_mode')=='pinned_views'
        if pinned and (not policy['view_hashes'] or any(policy['objects'][name]['type']!='view' for name in used)):
            raise Rejected('Este modo permite somente views aprovadas e imutáveis para o conector')
        check_views(kind, policy['objects'], used, policy.get('view_hashes',{}) if pinned else None)
        parameters=[]
        if secp:
            validated,parameters,dependencies=scoped_sql(validated,c,policy,grant,scope_rules)
            check_views(kind,policy['objects'],dependencies,policy.get('view_hashes',{}))
            kinds={scope_rules[n]['kind'] for n in used}
            access['scope']='own' if 'own' in kinds else ('team' if 'team' in kinds else 'organization')
        limit = min(request['limit'], policy['max_rows'])
        offset = request['offset']
        dialect = {'mssql':'tsql'}.get(kind, kind)
        inner = sqlglot.parse_one(validated, read=dialect)
        outer = exp.select('*').from_(inner.subquery('moara_readonly')).limit(limit + 1).offset(offset)
        if kind == 'mssql': outer = outer.order_by(exp.Literal.number(1))
        query = outer.sql(dialect=dialect)
        if secp:
            import psycopg
            with psycopg.RawCursor(db) as cursor:
                cursor.execute(query,parameters)
                columns=[v[0] for v in cursor.description];rows=cursor.fetchmany(limit+1)
            if evaluate(body['identity'])['fingerprint']!=grant['fingerprint']:raise Rejected('As permissões do SECP mudaram durante a consulta; execute novamente')
        else:columns, rows = fetch(db, query, max_rows=limit+1)
        result = safe_rows(columns, rows, limit)
        return {**result, 'objects': used, 'offset': offset,'limit':limit, 'next_offset': offset+limit if result['incomplete'] else None,
            'readonly_verified': True,**({'secp_access':access} if secp else {})}
