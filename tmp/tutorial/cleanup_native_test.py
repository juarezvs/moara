import importlib.util,json,ssl,urllib.request
from pathlib import Path
ROOT=Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
token=m.admin_session();ctx=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/moara-domain-root-ca.crt'))
def call(path,method=None):
 req=urllib.request.Request('https://moara.am.trf1.gov.br'+path,headers={'Authorization':'Bearer '+token},method=method)
 with urllib.request.urlopen(req,context=ctx,timeout=40) as r:return json.load(r)
identifier='e83269f5-5490-4696-ad14-08fc0bb907f8'
d=call('/api/v1/chats/'+identifier);chat=d['chat'];messages=chat.get('history',{}).get('messages',{}).values()
assert any(x.get('role')=='user' and 'Segundo o arquivo fictício anexado' in x.get('content','') for x in messages)
files=set()
for message in messages:
 if message.get('role')=='assistant':
  print(json.dumps({'synthetic_answer':message.get('content','')[:2000],'error':message.get('error'),'done':message.get('done')},ensure_ascii=False))
 for f in message.get('files',[]):
  if f.get('name')=='moara-teste-interface-ficticio.txt' and f.get('id'):files.add(f['id'])
for f in chat.get('files',[]):
 if f.get('name')=='moara-teste-interface-ficticio.txt' and f.get('id'):files.add(f['id'])
for fid in files:
 f=call('/api/v1/files/'+fid);assert f['filename']=='moara-teste-interface-ficticio.txt'
 call('/api/v1/files/'+fid,'DELETE')
call('/api/v1/chats/'+identifier,'DELETE')
print(json.dumps({'synthetic_chat_removed':True,'synthetic_files_removed':len(files)}))
call('/api/v1/auths/signout','POST')
