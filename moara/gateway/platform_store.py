"""Shared encrypted resource/version store with authorization before content access."""
import hashlib,json,uuid
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from .database import as_json
from .platform_contracts import validate_body

VISIBLE="""(r.owner_id=CAST(:actor AS uuid) OR EXISTS
 (SELECT 1 FROM moara.group_members gm WHERE gm.group_id=r.group_id AND gm.account_id=CAST(:actor AS uuid)))"""
def access_params(actor):
 return {'actor':str(actor.user_id),'interactive':actor.key_id is None,'sources':json.dumps(list(actor.allowed_sources or []))}

VISIBLE+=" AND (r.kind<>'document' OR :interactive OR CAST(r.id AS text) IN (SELECT jsonb_array_elements_text(CAST(:sources AS jsonb))))"

def seal(app,value):return app.state.settings.fernet().encrypt(as_json(jsonable_encoder(value)).encode()).decode()
def unseal(app,value):return json.loads(app.state.settings.fernet().decrypt(value.encode()))
def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def public(app,row,body=True):
 result={k:v for k,v in row.items() if k!='body'}
 if body:result['body']=unseal(app,row['body'])
 return result
async def get(app,actor,identifier,*,kind=None,write=False,conn=None,lock=False):
 sql='SELECT r.* FROM moara.resources r WHERE r.id=CAST(:id AS uuid) AND NOT r.archived AND '+VISIBLE
 if lock:sql+=' FOR UPDATE'
 row=await app.state.db.execute(sql,{'id':str(identifier),**access_params(actor)},one=True,conn=conn)
 if not row or (kind and row['kind']!=kind):raise HTTPException(404,'resource_not_found')
 if write and str(row['owner_id'])!=str(actor.user_id):raise HTTPException(403,'resource_owner_required')
 return public(app,row)
async def group_allowed(app,actor,group_id,conn=None):
 if group_id is None:return
 row=await app.state.db.execute('SELECT 1 FROM moara.group_members WHERE group_id=CAST(:group AS uuid) AND account_id=CAST(:actor AS uuid)',
  {'group':str(group_id),'actor':str(actor.user_id)},one=True,conn=conn)
 if not row:raise HTTPException(403,'group_membership_required')
async def references(app,actor,body):
 ids=[]
 for key in ('document_ids',):
  values=body.get(key,[])
  if not isinstance(values,list):raise HTTPException(422,'invalid_source_list')
  ids+=values
 if body.get('document_id'):ids.append(body['document_id'])
 for event in body.get('events',[]):ids.append(event['document_id'])
 for identifier in set(map(str,ids)):
  try:identifier=uuid.UUID(identifier)
  except (ValueError,TypeError):raise HTTPException(422,'invalid_source_identifier')
  await get(app,actor,identifier,kind='document')
 return sorted(set(map(str,ids)))
async def create(app,actor,kind,title,body,group_id=None,*,identifier=None,conn=None):
 validate_body(kind,body);await group_allowed(app,actor,group_id,conn)
 await references(app,actor,body)
 if conn is None:
  async with app.state.db.engine.begin() as c:return await create(app,actor,kind,title,body,group_id,identifier=identifier,conn=c)
 identifier=identifier or uuid.uuid4();encrypted=seal(app,body)
 await app.state.db.execute('''INSERT INTO moara.resources(id,kind,owner_id,group_id,title,body)
 VALUES(CAST(:id AS uuid),:kind,CAST(:owner AS uuid),CAST(:group AS uuid),:title,:body)''',
 {'id':str(identifier),'kind':kind,'owner':str(actor.user_id),'group':str(group_id) if group_id else None,'title':title,'body':encrypted},conn=conn)
 await app.state.db.execute('''INSERT INTO moara.resource_versions(resource_id,version,title,body,author_id)
 VALUES(CAST(:id AS uuid),1,:title,:body,CAST(:actor AS uuid))''',
 {'id':str(identifier),'title':title,'body':encrypted,'actor':str(actor.user_id)},conn=conn)
 if kind=='workflow':
  from .platform_schedules import configure
  await configure(app,actor,identifier,body,conn)
 await app.state.db.audit(actor,'resource.created',identifier,conn=conn)
 return {'id':str(identifier),'kind':kind,'version':1}
async def update(app,actor,identifier,title,body,group_id,version):
 async with app.state.db.engine.begin() as conn:
  row=await get(app,actor,identifier,write=True,conn=conn,lock=True)
  if row['version']!=version:raise HTTPException(409,'resource_version_conflict')
  validate_body(row['kind'],body);await references(app,actor,body);await group_allowed(app,actor,group_id,conn)
  encrypted=seal(app,body)
  await app.state.db.execute('''UPDATE moara.resources SET title=:title,body=:body,group_id=CAST(:group AS uuid),version=version+1,updated_at=now()
  WHERE id=CAST(:id AS uuid)''',{'id':str(identifier),'title':title,'body':encrypted,'group':str(group_id) if group_id else None},conn=conn)
  await app.state.db.execute('''INSERT INTO moara.resource_versions(resource_id,version,title,body,author_id)
  VALUES(CAST(:id AS uuid),:version,:title,:body,CAST(:actor AS uuid))''',
  {'id':str(identifier),'version':version+1,'title':title,'body':encrypted,'actor':str(actor.user_id)},conn=conn)
  if row['kind']=='workflow':
   from .platform_schedules import configure
   await configure(app,actor,identifier,body,conn)
  await app.state.db.audit(actor,'resource.updated',identifier,conn=conn)
 return {'id':str(identifier),'version':version+1}
