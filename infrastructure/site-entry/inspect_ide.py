"""Read catalogue and validate current native API tool transport; no key is printed."""
import json,pathlib,subprocess,importlib.util
root=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import asyncio,json,sys
import httpx
from moara.gateway.database import Database
from moara.gateway.settings import Settings
async def main():
 db=Database(Settings.load())
 profiles=await db.execute('SELECT id,name,manual_allowed,public,settings FROM moara.profiles WHERE enabled ORDER BY id')
 rows=await db.execute('SELECT display_name,capabilities FROM moara.models WHERE enabled AND installed')
 await db.dispose();print(json.dumps({'profiles':profiles,'models':rows},default=str))
 token=sys.stdin.read().strip()
 async with httpx.AsyncClient(timeout=180,trust_env=False) as client:
  headers={'Authorization':'Bearer '+token}
  tools=[{'type':'function','function':{'name':'read_project_file','description':'Read a synthetic software source file supplied by the IDE test client.','parameters':{'type':'object','properties':{'path':{'type':'string','enum':['example.py']}},'required':['path'],'additionalProperties':False}}}]
  messages=[{'role':'user','content':'For this software development test, inspect the code in example.py using the read_project_file tool. Do not invent the file contents.'}]
  body={'model':'general','assistant_id':'desenvolvedora','messages':messages,'tools':tools,'tool_choice':{'type':'function','function':{'name':'read_project_file'}},'max_tokens':128,'temperature':0}
  r=await client.post('http://localhost:8075/v1/chat/completions',headers=headers,json=body)
  value=r.json();calls=value.get('choices',[{}])[0].get('message',{}).get('tool_calls',[]) if r.status_code==200 else []
  print(json.dumps({'tool_status':r.status_code,'error':value.get('detail'),'calls':calls,'backend':value.get('moara',{}).get('execution_backend')}))
  if calls:
   messages+=[value['choices'][0]['message'],{'role':'tool','tool_call_id':calls[0]['id'],'content':'def add(a, b):\n    return a - b\n'}]
   body.update(messages=messages,tool_choice='none',max_tokens=256)
   r=await client.post('http://localhost:8075/v1/chat/completions',headers=headers,json=body)
   value=r.json();text=value.get('choices',[{}])[0].get('message',{}).get('content','') if r.status_code==200 else ''
   print(json.dumps({'roundtrip_status':r.status_code,'has_code_diagnosis':bool(text),'backend':value.get('moara',{}).get('execution_backend'),'sample':text[:300]}))
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session(),text=True,capture_output=True,timeout=450)
print(r.stdout)
if r.returncode:print('IDE_INSPECTION_FAILED: '+r.stderr.split('Call log:')[0][-700:])
raise SystemExit(r.returncode)
