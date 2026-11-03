"""Preserve ACLs and CPU alternatives while selecting the validated GPU model."""
import asyncio,json,sys
from types import SimpleNamespace
from moara.gateway.database import Database,as_json
from moara.gateway.settings import Settings

PRIMARY='63af8a56-5676-52b1-b969-887658bb937d'
async def main():
 db=Database(Settings.load())
 before={'profiles':await db.execute("SELECT * FROM moara.profiles WHERE id IN ('general','fast')"),
         'mappings':await db.execute("SELECT * FROM moara.profile_models WHERE profile_id IN ('general','fast')"),
         'bindings':await db.execute("SELECT b.id,b.legacy_alias FROM moara.execution_bindings b JOIN moara.profile_models pm ON pm.model_id=b.model_id WHERE pm.profile_id IN ('general','fast')")}
 print('CATALOG_BACKUP='+json.dumps(before,default=str),flush=True)
 async with db.engine.begin() as conn:
  primary=await db.execute('SELECT id FROM moara.models WHERE id=CAST(:id AS uuid) AND enabled AND installed',{'id':PRIMARY},one=True,conn=conn)
  assert primary,'Validated primary model unavailable'
  for old,cpu,name in [('general','gemma4-26b-cpu','Gemma 4 26B · CPU'),('fast','qwen3-8b-cpu','Qwen3 8B · CPU')]:
   await db.execute('''INSERT INTO moara.profiles(id,name,description,category,enabled,manual_allowed,public,allowed_subjects,allowed_groups,settings,legacy_compatible)
    SELECT :new,:name,'Alternativa no servidor de aplicação; preserva o modelo anterior à ativação da GPU.',category,enabled,manual_allowed,public,allowed_subjects,allowed_groups,
      (settings-'legacy_alias') || CAST(:extra AS jsonb),false FROM moara.profiles WHERE id=:old ON CONFLICT(id) DO NOTHING''',
    {'new':cpu,'name':name,'old':old,'extra':as_json({'auto_eligible':False})},conn=conn)
   await db.execute('''INSERT INTO moara.profile_models(profile_id,model_id,priority)
    SELECT :new,model_id,priority FROM moara.profile_models WHERE profile_id=:old AND model_id<>CAST(:primary AS uuid) ON CONFLICT DO NOTHING''',
    {'new':cpu,'old':old,'primary':PRIMARY},conn=conn)
   await db.execute('''UPDATE moara.execution_bindings SET legacy_alias=NULL WHERE model_id IN
    (SELECT model_id FROM moara.profile_models WHERE profile_id=:id) AND model_id<>CAST(:primary AS uuid)''',
    {'id':old,'primary':PRIMARY},conn=conn)
   await db.execute('DELETE FROM moara.profile_models WHERE profile_id=:id',{'id':old},conn=conn)
   await db.execute('INSERT INTO moara.profile_models(profile_id,model_id,priority) VALUES(:id,CAST(:model AS uuid),0)',{'id':old,'model':PRIMARY},conn=conn)
   await db.execute('''UPDATE moara.profiles SET name=:name,settings=(settings-'legacy_alias') || CAST(:extra AS jsonb),updated_at=now() WHERE id=:id''',
    {'id':old,'name':'Moara principal' if old=='general' else 'Respostas rápidas',
     'extra':as_json({'context_length':8192,'threads':12,'reasoning_effort':'none','auto_eligible':True})},conn=conn)
  await db.audit(SimpleNamespace(subject='deployment:nutec',key_id=None),'deployment.gpu.activate','gpu-20261029',conn=conn)
 print('CATALOG_ACTIVATED',flush=True)
 await db.dispose()
asyncio.run(main())
