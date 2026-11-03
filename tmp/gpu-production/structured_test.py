import httpx,json,time,asyncio
from moara.gateway.settings import Settings
from moara.gateway.database import Database,as_json
s=Settings.load();samples=[]
schema={'type':'object','properties':{'status':{'type':'string','enum':['ok']},'count':{'type':'integer','enum':[3]}},'required':['status','count'],'additionalProperties':False}
with httpx.Client(trust_env=False,timeout=180) as c:
 for fmt in [{'type':'json_object'},{'type':'json_schema','json_schema':{'name':'synthetic_status','strict':True,'schema':schema}}]:
  start=time.monotonic();r=c.post('http://gateway:8000/v1/chat/completions',headers={'Authorization':'Bearer '+s.llm_key},json={'model':'general','messages':[{'role':'user','content':'Retorne somente JSON com status igual a ok e count igual a 3.'}],'max_tokens':128,'temperature':0,'reasoning_effort':'none','response_format':fmt})
  r.raise_for_status();value=json.loads(r.json()['choices'][0]['message']['content']);assert value=={'status':'ok','count':3}
  assert r.headers['x-moara-inference-backend']=='gpu'
  samples.append({'format':fmt['type'],'seconds':time.monotonic()-start,'result':value,'backend':'gpu'})
async def activate():
 db=Database(s)
 row=await db.execute('SELECT capabilities FROM moara.models WHERE id=CAST(:id AS uuid)',{'id':'63af8a56-5676-52b1-b969-887658bb937d'},one=True)
 caps={**row['capabilities'],'structured_output':True,'validation_scope':'Synthetic text, tool calls and GPU JSON object/schema fixtures validated; generated output still requires review'}
 await db.execute('UPDATE moara.models SET capabilities=CAST(:caps AS jsonb),updated_at=now() WHERE id=CAST(:id AS uuid)',{'id':'63af8a56-5676-52b1-b969-887658bb937d','caps':as_json(caps)})
 await db.audit(None,'deployment.gpu.structured_validated','63af8a56-5676-52b1-b969-887658bb937d');await db.dispose()
asyncio.run(activate())
print(json.dumps({'synthetic_only':True,'samples':samples,'structured_output_enabled_after_validation':True}),flush=True)
