import subprocess
code=r'''
import ast,pathlib,json
for filename in ['chats.py','auths.py']:
 p=pathlib.Path('/app/backend/open_webui/routers')/filename;s=p.read_text();tree=ast.parse(s)
 for n in tree.body:
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
   routes=[ast.unparse(d) for d in n.decorator_list if 'router.' in ast.unparse(d)]
   if filename=='chats.py' and any(any(x in d for x in ['/list','/{id}','/{chat_id}']) for d in routes) or filename=='auths.py' and any(x in n.name for x in ['signin','ldap_auth']):
    print(json.dumps({'file':filename,'name':n.name,'routes':routes,'code':'\n'.join(s.splitlines()[n.lineno-1:min(n.end_lineno,n.lineno+75)])},ensure_ascii=True))
'''
r=subprocess.run(['docker','exec','-i','ai-server-webui-1','python','-'],input=code,text=True,capture_output=True,timeout=25)
print(r.stdout);print(r.stderr[-500:])
