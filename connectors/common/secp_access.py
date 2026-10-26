"""SECP access never derives from the Moara administrative transport role."""
from copy import deepcopy
import time
from fastapi import HTTPException

def application(row):return (row.get('semantic') or {}).get('dataset')=='secp_application'

async def identity(hub,user):
    cached=user.get('_secp_identity')
    if cached and time.monotonic()-cached[0]<1:return cached[1]
    if not user.get('ticket'):raise HTTPException(403,'O SECP exige uma sessão institucional verificada')
    response=await hub.HTTP.post('http://moara-gateway:8075/api/v1/internal/connectors/secp-identity',
        headers={'Authorization':'Bearer '+hub.KEY,'X-Moara-Execution-Ticket':user['ticket']},json={},timeout=15)
    if response.status_code!=200:
        try:detail=response.json().get('detail')
        except Exception:detail=None
        raise HTTPException(403,detail or 'Não foi possível verificar sua identidade institucional para o SECP')
    value=response.json()['identity'];user['_secp_identity']=(time.monotonic(),value)
    return value

async def grant(hub,row,user,profile=None,*,use_default=False):
    value=dict(await identity(hub,user))
    if profile is not None:value['profile']=profile
    if use_default:value['profile']=None
    return await hub.worker('postgres','authorize_secp',row['connection'],hub.store.decrypt(row['credential']),
        row.get('_base_policy',row['policy']),identity=value)

async def scope(hub,row,user):
    result=await grant(hub,row,user);baseline=row.get('_base_policy',row['policy'])
    selected={}
    for name,item in baseline['objects'].items():
        approved=result['objects'].get(name)
        if not approved:continue
        selected[name]={**item,'fields':[f for f in item['fields'] if f['name'] in approved['fields']]}
        selected[name]['support_only']=bool(approved.get('support_only'))
    if not selected:raise HTTPException(403,'Seu perfil ativo do SECP não autoriza dados desta seccional. Pergunte quais são seus perfis no SECP para conferir as opções atribuídas à sua conta.')
    row['_base_policy']=baseline;row['policy']={**baseline,'objects':selected,
        'view_hashes':{n:h for n,h in baseline.get('view_hashes',{}).items() if n in selected}}
    row['_secp_access']=result['access']
    semantic=deepcopy(row.get('semantic') or {});semantic['secp_access']={k:v for k,v in result['access'].items() if k!='fingerprint'}
    semantic['scope']='Live SECP RBAC, active assigned profile; rows and fields are restricted by the PostgreSQL worker before aggregation.'
    if semantic.get('organization_scope'):
        semantic['organization_scope']=[u for u in semantic['organization_scope'] if u in result['access']['organizations']]
    semantic['table_descriptions']={n:d for n,d in semantic.get('table_descriptions',{}).items() if n in selected}
    row['semantic']=semantic
    return row

async def revalidate(hub,evidence,user):
    for item in evidence:
        expected=item.get('secp_access',{}).get('fingerprint')
        if not expected:continue
        row=await hub.source(item['source_id'],user,active=True)
        if row.get('_secp_access',{}).get('fingerprint')!=expected:
            raise HTTPException(403,'O perfil ou o escopo do SECP mudou. Execute novamente a consulta com as permissões atuais.')
