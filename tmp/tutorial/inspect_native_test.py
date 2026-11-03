import importlib.util,json,ssl,urllib.request
from pathlib import Path
ROOT=Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
token=m.admin_session();ctx=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/moara-domain-root-ca.crt'))
def call(path,method=None):
 req=urllib.request.Request('https://moara.am.trf1.gov.br'+path,headers={'Authorization':'Bearer '+token},method=method)
 with urllib.request.urlopen(req,context=ctx,timeout=40) as r:return json.load(r)
try:
 listing=call('/api/v1/chats/?page=1')
 if isinstance(listing,dict):listing=listing.get('items',listing.get('data',[]))
 for item in listing[:5]:
  d=call('/api/v1/chats/'+item['id']);chat=d.get('chat',{});messages=list(chat.get('history',{}).get('messages',{}).values())
  if not any(x.get('role')=='user' and x.get('content','').startswith('Leia o início do arquivo fictício anexado com view_file') for x in messages):continue
  print(json.dumps({'synthetic_chat_id':item['id'],'messages':[{'role':x.get('role'),'done':x.get('done'),'content':x.get('content','')[:1500],'error':x.get('error'),'output_types':[o.get('type') for o in (x.get('output') or [])]} for x in messages]},ensure_ascii=False))
  break
 else:print('No active matching synthetic chat among recent entries.')
finally:call('/api/v1/auths/signout','POST')
