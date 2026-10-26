"""Fixed administrative jobs. Model output never becomes a host command."""
import asyncio
import base64
import hashlib
import json
import os
import time
import uuid
from types import SimpleNamespace
import httpx
from celery import Celery
from cryptography.fernet import Fernet
from .settings import secret,database_url
from .database import Database,as_json
from .model_catalog import APPROVED
from .bootstrap import NAMESPACE
from celery.signals import worker_ready

celery_app=Celery('moara',broker='redis://:'+secret('moara_redis_password')+'@moara-redis:6379/1')
celery_app.conf.update(task_serializer='json',accept_content=['json'],result_backend=None,task_ignore_result=True,
    task_acks_late=True,task_reject_on_worker_lost=True,worker_prefetch_multiplier=1,broker_connection_retry_on_startup=True,
    broker_transport_options={'visibility_timeout':6000,'socket_timeout':5,'socket_connect_timeout':5},
    task_soft_time_limit=5400,task_time_limit=5700,worker_hijack_root_logger=False,task_send_sent_event=False)

@worker_ready.connect
def start_presence(**kwargs):
    import threading
    from redis import Redis
    def pulse():
        client=Redis.from_url(celery_app.conf.broker_url,socket_timeout=3,socket_connect_timeout=3)
        while True:
            try:client.set('moara:worker:presence',str(int(time.time())),ex=45)
            except Exception:pass
            time.sleep(15)
    threading.Thread(target=pulse,daemon=True,name='moara-worker-presence').start()

def crypto():return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret('moara_crypto_key').encode()).digest()))

async def bind(db,http,model,context=8192,threads=12):
    row=await db.execute('SELECT * FROM moara.execution_bindings WHERE model_id=CAST(:id AS uuid) AND context_length=:context AND threads=:threads',
        {'id':str(model['id']),'context':context,'threads':threads},one=True)
    if row and row['ready']:return row
    identifier=uuid.uuid5(NAMESPACE,'binding:'+str(model['id'])+':'+str(context)+':'+str(threads))
    alias='moara-'+str(model['id']).split('-')[0]+'-'+str(context)+'-'+str(threads)+'t'
    # Derive additional contexts from an immutable existing execution alias,
    # preserving the old weights after the upstream download tag is updated.
    existing=await db.execute('SELECT tag FROM moara.execution_bindings WHERE model_id=CAST(:id AS uuid) AND ready ORDER BY created_at LIMIT 1',{'id':str(model['id'])},one=True)
    result=await http.post('http://moara-model-management:11434/api/create',json={'model':alias,'from':existing['tag'] if existing else model['tag'],
        'parameters':{'num_ctx':context,'num_thread':threads,'num_gpu':0},'stream':False},timeout=300)
    result.raise_for_status()
    await db.execute('''INSERT INTO moara.execution_bindings(id,model_id,provider,tag,context_length,threads,ready)
        VALUES(CAST(:id AS uuid),CAST(:model AS uuid),:provider,:tag,:context,:threads,true)
        ON CONFLICT(model_id,context_length,threads) DO UPDATE SET ready=true RETURNING id''',
        {'id':str(identifier),'model':str(model['id']),'provider':model['provider'],'tag':alias,'context':context,'threads':threads})
    return await db.execute('SELECT * FROM moara.execution_bindings WHERE id=CAST(:id AS uuid)',{'id':str(identifier)},one=True)

async def install(db,http,payload,job):
    approved=APPROVED.get(payload.get('catalog_id'))
    if not approved:raise ValueError('model_not_in_approved_catalog')
    existing=await db.execute("SELECT * FROM moara.models WHERE provider='ollama' AND settings->>'catalog_id'=:catalog ORDER BY created_at DESC LIMIT 1",{'catalog':payload['catalog_id']},one=True)
    if existing and existing['installed'] and payload.get('mode')!='update':
        return {'model_id':str(existing['id']),'already_installed':True,'activation_changed':False}
    last_update=0
    async with http.stream('POST','http://moara-model-management:11434/api/pull',json={'model':approved['tag'],'stream':True},timeout=1200) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line:continue
            value=json.loads(line)
            if value.get('error'):raise RuntimeError('model_download_rejected')
            if time.monotonic()-last_update>2:
                last_update=time.monotonic();total=value.get('total',0);done=value.get('completed',0)
                progress=min(85,int(done/total*85)) if total else 5
                await db.execute('UPDATE moara.jobs SET progress=:progress,updated_at=now() WHERE id=CAST(:id AS uuid)',{'id':str(job['id']),'progress':progress})
    show=await http.post('http://moara-model-management:11434/api/show',json={'model':approved['tag']});show.raise_for_status();details=show.json()
    tags=await http.get('http://moara-model-management:11434/api/tags');tags.raise_for_status()
    physical=next((r for r in tags.json()['models'] if r['name']==approved['tag']),None)
    if not physical:raise RuntimeError('downloaded_model_not_verified')
    source_digest=physical['digest']
    same=await db.execute("SELECT * FROM moara.models WHERE provider='ollama' AND settings->>'catalog_id'=:catalog AND COALESCE(settings->>'source_digest',digest)=:digest",{'catalog':payload['catalog_id'],'digest':source_digest},one=True)
    if same and same['installed']:return {'model_id':str(same['id']),'already_current':True,'activation_changed':False,'digest':same['digest']}
    tag=same['tag'] if same else 'moara-version-'+payload['catalog_id']+'-'+source_digest.removeprefix('sha256:')[:12]
    if tag!=approved['tag']:
        snapshot=await http.post('http://moara-model-management:11434/api/create',json={'model':tag,'from':approved['tag'],'stream':False},timeout=300)
        snapshot.raise_for_status()
        tags=await http.get('http://moara-model-management:11434/api/tags');tags.raise_for_status()
        physical=next((r for r in tags.json()['models'] if r['name']==tag or r['name']==tag+':latest'),None)
        if not physical:raise RuntimeError('model_version_snapshot_not_verified')
        tag=physical['name']
    identifier=same['id'] if same else uuid.uuid5(NAMESPACE,'ollama:'+tag+':'+physical['digest']);info=details.get('details',{})
    declared=details.get('capabilities',[])
    if approved['embedding'] and 'embedding' not in declared:raise RuntimeError('embedding_capability_missing')
    caps={'completion':'completion' in declared,'embedding':approved['embedding'],'tools':False,'vision':False,
        'structured_output':False,'declarations':declared,'validation_scope':'download verified; execution benchmark pending'}
    settings={'context_length':8192,'threads':12,'temperature':0.2,'max_tokens':512,'timeout':300,'catalog_id':payload['catalog_id'],
        'source_tag':approved['tag'],'source_digest':source_digest}
    await db.execute('''INSERT INTO moara.models(id,provider,tag,display_name,family,parameter_size,quantization,size_bytes,digest,declared_context,capabilities,settings,enabled)
        VALUES(CAST(:id AS uuid),'ollama',:tag,:name,:family,:parameters,:quantization,:size,:digest,:context,CAST(:caps AS jsonb),CAST(:settings AS jsonb),false)
        ON CONFLICT(provider,tag) DO UPDATE SET installed=true,enabled=false,capabilities=EXCLUDED.capabilities,updated_at=now()''',
        {'id':str(identifier),'tag':tag,'name':approved['name'],'family':info.get('family'),'parameters':info.get('parameter_size'),
            'quantization':info.get('quantization_level'),'size':physical['size'],'digest':physical['digest'],
            'context':next((v for k,v in details.get('model_info',{}).items() if k.endswith('.context_length')),None),
            'caps':as_json(caps),'settings':as_json(settings)})
    model=await db.execute('SELECT * FROM moara.models WHERE id=CAST(:id AS uuid)',{'id':str(identifier)},one=True)
    binding=await bind(db,http,model)
    return {'model_id':str(identifier),'binding_id':str(binding['id']),'digest':physical['digest'],'installed':True,
        'active':False,'next_step':'Run an authorized execution benchmark before activation','embedding':approved['embedding']}

async def benchmark(db,http,payload,job):
    identifier=uuid.UUID(payload['model_id'])
    model=await db.execute('SELECT * FROM moara.models WHERE id=CAST(:id AS uuid) AND installed',{'id':str(identifier)},one=True)
    if not model:raise ValueError('model_not_installed')
    approved=APPROVED.get(model['settings'].get('catalog_id'),{})
    embedding=model['capabilities'].get('embedding',False)
    contexts=payload.get('contexts',[8192]);threads=payload.get('threads',[12])
    if not set(contexts)<={4096,8192} or not set(threads)<={12,16}:raise ValueError('benchmark_configuration_not_allowed')
    cases=['embedding'] if embedding else ['text']+(['code'] if approved.get('category')=='coding' else [])
    if not embedding and 'tools' in model['capabilities'].get('declarations',[]):cases+=['tool']
    records=[];total=len(contexts)*len(threads)*len(cases);done=0
    for context in contexts:
        for count in threads:
            binding=await bind(db,http,model,context,count)
            for case in cases:
                response=await http.post('http://gateway:8000/internal/benchmark',json={'binding_id':str(binding['id']),'case':case},
                    headers={'Authorization':'Bearer '+secret('moara_llm_key')},timeout=1260)
                response.raise_for_status();result=response.json()
                parameters={'context_length':context,'threads':count,'case':case,'concurrency':1,'provider':model['provider'],
                    'model_digest':model['digest'],'binding_id':str(binding['id']),'numa_affinity':'not enforced; rootless cpuset unavailable'}
                await db.execute('''INSERT INTO moara.benchmark_samples(job_id,model_id,parameters,metrics,quality)
                    VALUES(CAST(:job AS uuid),CAST(:model AS uuid),CAST(:parameters AS jsonb),CAST(:metrics AS jsonb),CAST(:quality AS jsonb))''',
                    {'job':str(job['id']),'model':str(identifier),'parameters':as_json(parameters),'metrics':as_json(result['metrics']),'quality':as_json(result['quality'])})
                records.append({**result,'parameters':parameters});done+=1
                await db.execute('UPDATE moara.jobs SET progress=:progress,updated_at=now() WHERE id=CAST(:id AS uuid)',{'id':str(job['id']),'progress':int(done/total*95)})
    baseline=[r for r in records if r['parameters']['context_length']==8192 and r['parameters']['threads']==12]
    required=[r for r in baseline if r['case']!='tool'];passed=bool(required) and all(r['quality']['passed'] for r in required)
    tools=any(r['case']=='tool' and r['quality']['passed'] for r in baseline)
    caps={**model['capabilities'],'tools':tools if baseline else model['capabilities'].get('tools',False),
        'validation_scope':'fixed synthetic fixtures, measured execution; no claim of full software correctness'}
    await db.execute('UPDATE moara.models SET capabilities=CAST(:caps AS jsonb),updated_at=now() WHERE id=CAST(:id AS uuid)',{'id':str(identifier),'caps':as_json(caps)})
    # Existing profiles and activation remain unchanged; new candidates are only enabled after a passing baseline.
    if passed and approved:
        binding=await bind(db,http,model)
        if embedding:
            dimension=required[0]['quality']['dimension']
            await db.execute('''INSERT INTO moara.embedding_indexes(id,model_id,binding_id,dimension,digest)
                VALUES(CAST(:id AS uuid),CAST(:model AS uuid),CAST(:binding AS uuid),:dimension,:digest) ON CONFLICT(model_id,digest) DO NOTHING''',
                {'id':str(uuid.uuid4()),'model':str(identifier),'binding':str(binding['id']),'dimension':dimension,'digest':model['digest']})
        else:
            await db.execute('UPDATE moara.models SET enabled=true WHERE id=CAST(:id AS uuid)',{'id':str(identifier)})
            owner=await db.execute('SELECT subject FROM moara.accounts WHERE id=CAST(:id AS uuid)',{'id':str(job['account_id'])},one=True)
            profile=model['settings']['catalog_id']
            previous=await db.execute('SELECT id FROM moara.profiles WHERE id=:id',{'id':profile},one=True)
            old_mapping=await db.execute('SELECT profile_id FROM moara.profile_models WHERE profile_id=:profile AND model_id=CAST(:model AS uuid)',{'profile':profile,'model':str(identifier)},one=True)
            updated_version=bool(previous and not old_mapping)
            if updated_version:profile+='-'+model['digest'].removeprefix('sha256:')[:8]
            await db.execute('''INSERT INTO moara.profiles(id,name,category,allowed_subjects,settings)
                VALUES(:id,:name,:category,CAST(:subjects AS jsonb),CAST(:settings AS jsonb)) ON CONFLICT(id) DO NOTHING''',
                {'id':profile,'name':model['display_name']+(' · '+model['digest'].removeprefix('sha256:')[:8] if updated_version else ''),'category':approved['category'],'subjects':as_json([owner['subject']]),'settings':as_json({**{k:v for k,v in model['settings'].items() if k in {'context_length','threads','temperature','max_tokens','timeout','reasoning_effort'}},'auto_eligible':not updated_version})})
            await db.execute('INSERT INTO moara.profile_models(profile_id,model_id) VALUES(:profile,CAST(:model AS uuid)) ON CONFLICT DO NOTHING',{'profile':profile,'model':str(identifier)})
    return {'model_id':str(identifier),'baseline_passed':passed,'records':records,'sample_count':len(records),
        'activation_changed':bool(passed and approved and not embedding),'existing_embedding_index_untouched':True,
        'percentiles':'Individual samples; no population latency confidence claim'}

async def remove(db,http,payload,job):
    identifier=uuid.UUID(payload['model_id'])
    async with db.engine.begin() as conn:
        model=await db.execute('SELECT * FROM moara.models WHERE id=CAST(:id AS uuid) FOR UPDATE',{'id':str(identifier)},one=True,conn=conn)
        if not model or model['protected'] or model['digest']!=payload.get('expected_digest') or model['display_name']!=payload.get('confirmation_name'):
            raise PermissionError('model_removal_not_authorized')
        used=await db.execute('''SELECT p.id FROM moara.profile_models pm JOIN moara.profiles p ON p.id=pm.profile_id
            WHERE pm.model_id=CAST(:id AS uuid) AND p.enabled LIMIT 1''',{'id':str(identifier)},one=True,conn=conn)
        if used:raise PermissionError('model_has_enabled_profiles')
        await db.execute('UPDATE moara.models SET enabled=false WHERE id=CAST(:id AS uuid)',{'id':str(identifier)},conn=conn)
        bindings=await db.execute('SELECT * FROM moara.execution_bindings WHERE model_id=CAST(:id AS uuid)',{'id':str(identifier)},conn=conn)
    for binding in bindings:
        if binding['legacy_alias'] or not binding['tag'].startswith('moara-'):raise PermissionError('protected_execution_binding')
        response=await http.request('DELETE','http://moara-model-management:11434/api/delete',json={'model':binding['tag']},timeout=60)
        if response.status_code not in (200,404):response.raise_for_status()
    other=await db.execute('SELECT id FROM moara.models WHERE provider=:provider AND tag=:tag AND id<>CAST(:id AS uuid) AND installed LIMIT 1',
        {'id':str(identifier),'provider':model['provider'],'tag':model['tag']},one=True)
    if not other:
        response=await http.request('DELETE','http://moara-model-management:11434/api/delete',json={'model':model['tag']},timeout=60)
        if response.status_code not in (200,404):response.raise_for_status()
    async with db.engine.begin() as conn:
        await db.execute('UPDATE moara.models SET installed=false,enabled=false,updated_at=now() WHERE id=CAST(:id AS uuid)',{'id':str(identifier)},conn=conn)
        await db.execute('UPDATE moara.execution_bindings SET ready=false WHERE model_id=CAST(:id AS uuid)',{'id':str(identifier)},conn=conn)
        await db.execute('UPDATE moara.embedding_indexes SET active=false WHERE model_id=CAST(:id AS uuid)',{'id':str(identifier)},conn=conn)
    return {'model_id':str(identifier),'removed':True,'existing_models_preserved':True,'historical_metrics_retained':True}

async def execute(identifier):
    identifier=uuid.UUID(identifier);db=Database(SimpleNamespace(db_url=database_url('worker')));lease=None;operation=None
    try:
        row=await db.execute('''UPDATE moara.jobs SET status='running',started_at=COALESCE(started_at,now()),updated_at=now(),attempts=attempts+1,
            lease_until=now()+interval '90 seconds' WHERE id=CAST(:id AS uuid) AND status='queued' AND NOT cancel_requested RETURNING *''',{'id':str(identifier)},one=True)
        if not row:return
        required={'model.install':'models.install','model.update':'models.install','model.remove':'models.remove','model.benchmark':'benchmarks.run'}.get(row['kind'])
        rights=await db.execute('''SELECT r.permissions FROM moara.roles r JOIN moara.account_roles ar ON ar.role_id=r.id
            JOIN moara.accounts a ON a.id=ar.account_id WHERE a.id=CAST(:id AS uuid) AND a.active''',{'id':str(row['account_id'])})
        permissions={p for r in rights for p in r['permissions']}
        if not required or ('*' not in permissions and required not in permissions):raise PermissionError('job_authorization_revoked')
        payload=json.loads(crypto().decrypt(row['payload'].encode()))
        async with httpx.AsyncClient(trust_env=False,follow_redirects=False,timeout=httpx.Timeout(30,connect=5)) as http:
            handler={'model.install':install,'model.update':install,'model.benchmark':benchmark,'model.remove':remove}[row['kind']]
            operation=asyncio.create_task(handler(db,http,payload,row))
            async def heartbeat():
                try:
                    while not operation.done():
                        state=await db.execute('UPDATE moara.jobs SET lease_until=now()+interval \'90 seconds\',updated_at=now() WHERE id=CAST(:id AS uuid) RETURNING cancel_requested',{'id':str(identifier)},one=True)
                        permission=await db.execute('''SELECT EXISTS(SELECT 1 FROM moara.accounts a JOIN moara.account_roles ar ON ar.account_id=a.id
                            JOIN moara.roles r ON r.id=ar.role_id WHERE a.id=CAST(:id AS uuid) AND a.active
                            AND (r.permissions ? '*' OR r.permissions ? :permission)) AS permitted''',{'id':str(row['account_id']),'permission':required},one=True)
                        if state['cancel_requested'] or not permission['permitted']:operation.cancel();return
                        await asyncio.sleep(2)
                except Exception:operation.cancel()
            lease=asyncio.create_task(heartbeat());result=await operation
        await db.execute('''UPDATE moara.jobs SET status='completed',progress=100,result=:result,error_code=NULL,finished_at=now(),updated_at=now(),lease_until=NULL
            WHERE id=CAST(:id AS uuid)''',{'id':str(identifier),'result':crypto().encrypt(as_json(result).encode()).decode()})
    except asyncio.CancelledError:
        await db.execute("UPDATE moara.jobs SET status='cancelled',finished_at=now(),updated_at=now(),lease_until=NULL WHERE id=CAST(:id AS uuid)",{'id':str(identifier)})
    except Exception as error:
        # Type only: provider errors and SQL parameters never enter operational logs.
        await db.execute("UPDATE moara.jobs SET status='failed',error_code=:error,finished_at=now(),updated_at=now(),lease_until=NULL WHERE id=CAST(:id AS uuid)",{'id':str(identifier),'error':type(error).__name__})
    finally:
        if lease:lease.cancel();await asyncio.gather(lease,return_exceptions=True)
        await db.dispose()

@celery_app.task(name='moara.execute')
def execute_job(identifier):asyncio.run(execute(identifier))
