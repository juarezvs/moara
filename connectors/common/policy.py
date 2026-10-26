"""A deliberately bounded SELECT dialect. Credentials remain a mandatory second layer."""
import hashlib
import ipaddress
import json
import re
import socket
from datetime import date
import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify

DIALECTS = {'postgres': 'postgres', 'mysql': 'mysql', 'mssql': 'tsql', 'oracle': 'oracle', 'sqlite': 'sqlite'}
IDENTIFIER = re.compile(r'^[A-Za-z_][A-Za-z0-9_$#]{0,127}$')
FUNCTIONS = {'Count', 'Sum', 'Avg', 'Min', 'Max', 'Lower', 'Upper', 'Length', 'Abs', 'Round', 'Coalesce', 'Cast', 'Extract'}
NODES = set(('Select Union Intersect Except Subquery With CTE Table TableAlias Identifier Column Star Alias '
    'From Join Where Group Having Order Ordered Limit Offset Literal Null Boolean Distinct '
    'EQ NEQ GT GTE LT LTE And Or Not Paren Between In Is Like ILike Escape Add Sub Mul Div Mod Neg '
    'Case If When DataType DataTypeParam Tuple Window WindowSpec RowNumber Rank DenseRank '
    'DPipe ConcatParen DateStrToDate').split()) | FUNCTIONS

class Rejected(ValueError):
    pass

def allowed_objects(policy):
    result = {}
    for name, item in policy['objects'].items():
        if name in policy.get('blocked_objects', []): continue
        fields = item.get('fields', [])
        fields = [f for f in fields if policy.get('allow_sensitive') or not f.get('sensitive', False)]
        if fields: result[name] = {**item, 'fields': fields}
    return result

def validate_sql(kind, query, policy):
    if not isinstance(query, str) or not query.strip() or len(query) > 16000: raise Rejected('Consulta SQL inválida')
    dialect = DIALECTS[kind]
    try:
        parsed = sqlglot.parse(query, read=dialect)
        if len(parsed) != 1 or not isinstance(parsed[0], (exp.Select, exp.Union, exp.Intersect, exp.Except)):
            raise Rejected('Somente uma consulta SELECT é permitida')
        tree = parsed[0]
        for node in tree.walk():
            if type(node).__name__ not in NODES or node.comments:
                raise Rejected('Construção ou função SQL não permitida: ' + type(node).__name__)
            if type(node).__name__=='DateStrToDate':
                if not isinstance(node.this,exp.Literal) or not node.this.is_string or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',node.this.this):
                    raise Rejected('Use somente datas literais ISO no formato DATE YYYY-MM-DD')
                try:date.fromisoformat(node.this.this)
                except ValueError:raise Rejected('Data literal inválida') from None
        objects = allowed_objects(policy)
        ctes = {n.alias_or_name.lower() for n in tree.find_all(exp.CTE)}
        used = []
        schema = {}
        for name, item in objects.items():
            parts = name.split('.')
            if len(parts) != 2 or not all(IDENTIFIER.fullmatch(p) for p in parts): continue
            schema.setdefault(parts[0], {})[parts[1]] = {f['name']: 'UNKNOWN' for f in item['fields']}
        for table in tree.find_all(exp.Table):
            if not table.db and table.name.lower() in ctes: continue
            name = table.db + '.' + table.name
            if table.catalog or name not in objects or not all(IDENTIFIER.fullmatch(p) for p in name.split('.')):
                raise Rejected('Objeto não autorizado; use schema.objeto')
            used.append(name)
        if not used: raise Rejected('A consulta deve ler um objeto autorizado')
        tree = qualify(tree, dialect=dialect, schema=schema,
            validate_qualify_columns=True, quote_identifiers=True, identify=True)
        # Recheck expressions introduced by qualification, including expanded stars.
        if any(type(n).__name__ not in NODES for n in tree.walk()): raise Rejected('Expressão não permitida')
        return tree.sql(dialect=dialect), sorted(set(used))
    except Rejected: raise
    except Exception: raise Rejected('SQL ou campos inválidos para os objetos autorizados') from None

def query_fingerprint(query):
    raw = json.dumps(query, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()

def masked_query(kind, query):
    if not isinstance(query, str):
        return {'keys': sorted(query), 'values': '[MASCARADOS]'}
    try:
        tree = sqlglot.parse_one(query, read=DIALECTS.get(kind))
        for literal in list(tree.find_all(exp.Literal)):
            literal.replace(exp.Literal.string('[MASCARADO]'))
        return tree.sql()[:2000]
    except Exception: return '[CONSULTA RECUSADA]'

def validate_ip(value, forbidden):
    address = ipaddress.ip_address(value)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped: address = address.ipv4_mapped
    if address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified or address.is_reserved:
        raise Rejected('Endereço de rede não permitido')
    if any(address in ipaddress.ip_network(n) for n in forbidden if address.version == ipaddress.ip_network(n).version):
        raise Rejected('Rede de infraestrutura não permitida')
    return str(address)

def pinned_ip(connection, forbidden=()):
    host = connection['host']
    if not host or any(c in host for c in '/@;\\\r\n'): raise Rejected('Host inválido')
    addresses = {validate_ip(r[4][0], forbidden) for r in socket.getaddrinfo(host, connection['port'], type=socket.SOCK_STREAM)}
    approved = set(connection.get('approved_ips', []))
    if not addresses or not addresses.issubset(approved): raise Rejected('Aprovação de endereço ausente ou DNS alterado; teste novamente')
    return sorted(addresses)[0]

def safe_rows(columns, rows, limit):
    output = []
    truncated = len(rows) > limit
    used = 0
    for row in rows[:limit]:
        cells = []
        for cell in row:
            if cell is None or isinstance(cell, (bool, int, float)): value = cell
            else: value = str(cell)[:512]
            cells.append(value)
        used += len(json.dumps(cells, default=str))
        if used > 200000: truncated = True; break
        output.append(cells)
    return {'columns': columns, 'rows': output, 'row_count': len(output), 'incomplete': truncated,
            'untrusted_data': True}
