"""Exercise actual managed update and removal, removing only an owned test alias."""
import importlib.util
import json
import ssl
import subprocess
import time
import urllib.request
import urllib.error
import uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
checks={}
def check(name,value):
    checks[name]=bool(value)
    if not value:raise AssertionError(name)

def main():
    spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    token=module.admin_session();tls=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/ai-root-ca.crt'))
    def request(path,body=None):
        r=urllib.request.Request('https://localhost:8443/moara/api/v1/'+path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(r,context=tls,timeout=30) as value:return value.status,json.load(value)
        except urllib.error.HTTPError as e:return e.code,json.load(e)
    def wait(job):
        end=time.monotonic()+180
        while True:
            status,value=request('jobs/'+job)
            if value['status'] in ('completed','failed','cancelled'):return value
            if time.monotonic()>end:raise TimeoutError('owned_model_job')
            time.sleep(2)
    status,before=request('models');check('real_inventory_accessible',status==200)
    preserved={m['id']:m['digest'] for m in before if m['installed']}
    protected=next(m for m in before if m['protected'])
    base={'model_id':protected['id'],'expected_digest':protected['digest'],'confirmation_name':protected['display_name'],'idempotency_key':'qa-protected-'+uuid.uuid4().hex}
    check('legacy_model_removal_denied',request('admin/model-removals',base)[0]==409)
    approved=next(m for m in before if m['settings'].get('catalog_id')=='gemma4-12b')
    body={'model_id':approved['id'],'expected_digest':approved['digest'],'idempotency_key':'qa-update-'+uuid.uuid4().hex}
    status,job=request('admin/model-updates',body);check('approved_update_queued',status==202)
    updated=wait(job['id']);check('actual_update_completed',updated['status']=='completed')
    check('unchanged_digest_keeps_activation',updated['result'].get('already_current') and updated['result']['activation_changed'] is False)
    check('active_profile_blocks_removal',request('admin/model-removals',{**body,'confirmation_name':approved['display_name'],'idempotency_key':'qa-active-'+uuid.uuid4().hex})[0]==409)
    # This fixed alias points at already downloaded embedding weights; it never
    # overwrites the requested model or a live execution binding.
    seed='''import asyncio,json,uuid,httpx
from types import SimpleNamespace
from moara.gateway.database import Database,as_json
from moara.gateway.settings import database_url
async def main():
 db=Database(SimpleNamespace(db_url=database_url('worker')))
 tag='moara-qa-removal-20261020:latest';identifier=uuid.uuid5(uuid.NAMESPACE_URL,'moara-real-removal-qa-20261020')
 old=await db.execute('SELECT settings FROM moara.models WHERE id=CAST(:id AS uuid)',{'id':str(identifier)},one=True)
 if old and old['settings'].get('fixture')!='model-removal-20261020':raise RuntimeError('Unowned fixture collision')
 async with httpx.AsyncClient(trust_env=False,timeout=60) as http:
  r=await http.post('http://moara-model-management:11434/api/create',json={'model':tag,'from':'qwen3-embedding:0.6b','stream':False});r.raise_for_status()
  r=await http.get('http://moara-model-management:11434/api/tags');r.raise_for_status()
  model=next(m for m in r.json()['models'] if m['name']==tag)
 await db.execute("INSERT INTO moara.models(id,provider,tag,display_name,digest,size_bytes,capabilities,settings,enabled,protected) VALUES(CAST(:id AS uuid),'ollama',:tag,'Validacao descartavel de remocao',:digest,:size,CAST(:caps AS jsonb),CAST(:settings AS jsonb),false,false) ON CONFLICT(id) DO UPDATE SET installed=true,enabled=false",{'id':str(identifier),'tag':tag,'digest':model['digest'],'size':model['size'],'caps':as_json({'embedding':True}),'settings':as_json({'fixture':'model-removal-20261020'})})
 await db.dispose();print(json.dumps({'id':str(identifier),'digest':model['digest'],'name':'Validacao descartavel de remocao'}))
asyncio.run(main())
'''
    result=subprocess.run(['docker','exec','-i','ai-server-moara-worker-1','python','-'],input=seed,text=True,capture_output=True,check=True)
    fixture=json.loads(result.stdout)
    body={'model_id':fixture['id'],'expected_digest':fixture['digest'],'confirmation_name':'wrong','idempotency_key':'qa-remove-'+uuid.uuid4().hex}
    check('exact_name_confirmation_required',request('admin/model-removals',body)[0]==409)
    status,job=request('admin/model-removals',{**body,'confirmation_name':fixture['name']})
    check('owned_fixture_removal_queued',status==202)
    removed=wait(job['id']);check('actual_worker_removal_completed',removed['status']=='completed' and removed['result']['removed'])
    status,after=request('models');live={m['id']:m['digest'] for m in after if m['installed']}
    check('all_original_models_preserved',live==preserved)
    check('removed_fixture_retains_audit_metadata',any(m['id']==fixture['id'] and not m['installed'] for m in after))
    probe="import urllib.request,json;v=json.load(urllib.request.urlopen('http://moara-model-management:11434/api/tags'));print(json.dumps({'fixture_present':any(m['name']=='moara-qa-removal-20261020:latest' for m in v['models'])}))"
    result=subprocess.run(['docker','exec','ai-server-moara-worker-1','python','-c',probe],capture_output=True,text=True,check=True)
    check('actual_ollama_test_alias_removed',not json.loads(result.stdout)['fixture_present'])
    return {'passed':True,'checks':checks,'scope':'actual API/jobs/worker/Ollama; only fixed synthetic alias removed; installed original models preserved'}

if __name__=='__main__':
    try:report=main()
    except Exception as error:report={'passed':False,'checks':checks,'failure_type':type(error).__name__}
    (ROOT/'docs/runtime/moara-model-operations-acceptance.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report));raise SystemExit(0 if report['passed'] else 1)
