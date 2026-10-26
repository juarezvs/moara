"""A supporting dimension is not an independent grant to the employee register."""
import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import traverse_scope
from common.policy import Rejected

REFERENCES={'orgaos','unidades_organizacionais','cargos','categorias_pessoas'}

def conjunctive_equalities(condition):
    if isinstance(condition,exp.Paren):yield from conjunctive_equalities(condition.this)
    elif isinstance(condition,exp.And):
        yield from conjunctive_equalities(condition.this)
        yield from conjunctive_equalities(condition.expression)
    elif isinstance(condition,exp.EQ):yield condition

def validate_support_joins(query,policy,relations):
    if not any(v.get('support_only') for v in policy['objects'].values()):return
    tree=sqlglot.parse_one(query,read='postgres')
    for scope in traverse_scope(tree):
        physical={a:(t.db+'.'+t.name) for a,t in scope.sources.items() if isinstance(t,exp.Table) and t.db+'.'+t.name in policy['objects']}
        restricted={a for a,n in physical.items() if policy['objects'][n].get('support_only')}
        if not restricted:continue
        anchors={a for a,n in physical.items() if a not in restricted and n.split('.',1)[1] not in REFERENCES}
        graph={a:set() for a in physical}
        for join in scope.expression.args.get('joins',[]):
            if join.args.get('side') or str(join.args.get('kind','')).upper() in {'CROSS','OUTER'}:continue
            condition=join.args.get('on')
            if condition is None or condition.find(exp.Or):continue
            for equality in conjunctive_equalities(condition):
                left,right=equality.this,equality.expression
                if not isinstance(left,exp.Column) or not isinstance(right,exp.Column) or left.table not in physical or right.table not in physical:continue
                a,b=physical[left.table].split('.',1)[1],physical[right.table].split('.',1)[1]
                if any((a,left.name,b,right.name)==(r['origin'],r['field'],r['target'],r['key']) or (b,right.name,a,left.name)==(r['origin'],r['field'],r['target'],r['key']) for r in relations):
                    graph[left.table].add(right.table);graph[right.table].add(left.table)
        reached=set(anchors);pending=list(anchors)
        while pending:
            for alias in graph[pending.pop()]-reached:reached.add(alias);pending.append(alias)
        if not restricted<=reached:raise Rejected('Dimensões de apoio exigem INNER JOIN por chave verificada com um conjunto de dados autorizado; não concedem acesso independente ao cadastro de pessoas')
