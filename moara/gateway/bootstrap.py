import json
import os
import uuid
from pathlib import Path
from .database import as_json

NAMESPACE=uuid.UUID('ab53c40b-6e40-43b3-86b2-d5d3c5caf895')

async def seed(db,auth):
    path=Path(os.getenv('MOARA_BOOTSTRAP_CATALOG','/run/secrets/moara_bootstrap_catalog.json'))
    if not path.exists():
        if os.getenv('MOARA_BOOTSTRAP_REQUIRED')=='true':raise RuntimeError('Required preserved catalog is not mounted')
        return
    source=json.loads(path.read_text())
    for account in source['accounts']:
        if account['role'] in ('admin','user'):await auth.upsert_legacy(account)
    by_alias={m['id']:m for m in source['models']}
    async with db.engine.begin() as conn:
        for group in source['groups']:
            await db.execute('INSERT INTO moara.groups(id,name) VALUES(CAST(:id AS uuid),:name) ON CONFLICT(id) DO NOTHING',
                {'id':group['id'],'name':group['name']},conn=conn)
        # Flatten effective inherited membership, preserving the legacy group IDs.
        parents={g['id']:g.get('parent_group_id') for g in source['groups']}
        for member in source['group_members']:
            node=member['group_id'];seen=set()
            while node and node not in seen:
                seen.add(node)
                await db.execute('''INSERT INTO moara.group_members(group_id,account_id) SELECT CAST(:group AS uuid),id FROM moara.accounts
                    WHERE legacy_id=CAST(:user AS uuid) ON CONFLICT DO NOTHING''',{'group':node,'user':member['user_id']},conn=conn)
                node=parents.get(node)
        for model in source['physical_models']:
            alias=model['alias'];old=by_alias.get(alias,{});details=model['details']
            identifier=uuid.uuid5(NAMESPACE,model['provider']+':'+model['tag'])
            # Tool availability is distinguished from upstream declarations.
            fast_validation=source.get('validation',{}).get('fast',{})
            tools=alias in {'coding','general','llama31-70b','llama33-70b'} or (alias=='fast' and fast_validation.get('single_native_tool_test') is True)
            caps={'completion':'completion' in model['declared_capabilities'],
                'tools':tools and 'tools' in model['declared_capabilities'],
                'vision':'vision' in model['declared_capabilities'],'embedding':'embedding' in model['declared_capabilities'],
                'structured_output':alias in {'coding','general'},'declarations':model['declared_capabilities'],
                'validation_scope':'single native tool with reasoning_effort=none; SQL planning not enabled' if alias=='fast' and tools else 'legacy acceptance reports'}
            settings={'context_length':8192,'threads':12,'temperature':0.2,'max_tokens':512,
                'timeout':1200 if model['provider']=='ollama-specialists' else 300,'legacy_alias':alias}
            if alias=='fast':settings['reasoning_effort']='none'
            owners=['webui:'+old['user_id']] if old.get('user_id') else []
            groups=[];public=False
            for grant in source['grants']:
                if grant['resource_id']!=alias or grant['permission'] not in ('read','write'):continue
                if grant['principal_type']=='anyone' or grant['principal_id']=='*':public=True
                elif grant['principal_type']=='user':owners.append('webui:'+grant['principal_id'])
                elif grant['principal_type']=='group':groups.append(grant['principal_id'])
            await db.execute('''INSERT INTO moara.models(id,provider,tag,display_name,family,parameter_size,quantization,size_bytes,digest,
                declared_context,capabilities,settings,protected) VALUES(CAST(:id AS uuid),:provider,:tag,:name,:family,:parameters,:quantization,:size,:digest,
                :context,CAST(:caps AS jsonb),CAST(:settings AS jsonb),true) ON CONFLICT(provider,tag) DO NOTHING''',
                {'id':str(identifier),'provider':model['provider'],'tag':model['tag'],'name':model.get('technical_name') or old.get('name') or alias,'family':details.get('family'),
                    'parameters':details.get('parameter_size'),'quantization':details.get('quantization_level'),'size':model['size_bytes'],'digest':model['digest'],
                    'context':details.get('context_length'),'caps':as_json(caps),'settings':as_json(settings)},conn=conn)
            binding=uuid.uuid5(NAMESPACE,'binding:'+str(identifier)+':8192:12')
            await db.execute('''INSERT INTO moara.execution_bindings(id,model_id,provider,tag,context_length,threads,ready,legacy_alias)
                VALUES(CAST(:id AS uuid),CAST(:model AS uuid),:provider,:tag,8192,12,true,:alias) ON CONFLICT DO NOTHING''',
                {'id':str(binding),'model':str(identifier),'provider':model['provider'],'tag':model['tag'],'alias':alias},conn=conn)
            await db.execute('''INSERT INTO moara.profiles(id,name,category,enabled,public,allowed_subjects,allowed_groups,settings,legacy_compatible)
                VALUES(:id,:name,:category,:enabled,:public,CAST(:owners AS jsonb),CAST(:groups AS jsonb),CAST(:settings AS jsonb),true) ON CONFLICT(id) DO NOTHING''',
                {'id':alias,'name':old.get('name') or alias,'category':'coding' if alias in {'coding','qwen25-coder-32b','deepseek-coder-v2-lite'} else 'fast' if alias=='fast' else 'general',
                    'enabled':bool(old.get('is_active',True)),'public':public,'owners':as_json(sorted(set(owners))),'groups':as_json(groups),'settings':as_json(settings)},conn=conn)
            # Initial import must not restore an old mapping after an operator
            # deliberately changes the model behind an existing profile.
            await db.execute('''INSERT INTO moara.profile_models(profile_id,model_id,priority)
                SELECT CAST(:profile AS varchar(64)),CAST(:model AS uuid),0 WHERE NOT EXISTS
                (SELECT 1 FROM moara.profile_models WHERE profile_id=CAST(:profile AS varchar(64))) ON CONFLICT DO NOTHING''',
                {'profile':alias,'model':str(identifier)},conn=conn)
