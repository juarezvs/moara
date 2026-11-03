import subprocess
code=r'''
import ast,pathlib,json
base=pathlib.Path('/app/backend/open_webui')
for p in [base/'routers/chats.py',base/'routers/auths.py']:
 s=p.read_text();tree=ast.parse(s)
 for n in tree.body:
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
   if n.name in ('get_chat_by_id','signin'):
    text='\n'.join(s.splitlines()[n.lineno-1:n.end_lineno])
    if n.name=='signin':text='\n'.join(line for line in text.splitlines() if any(k in line.lower() for k in ['ldap','mfa','totp','challenge','moara','authenticate','form_data','sign_in']))
    print(json.dumps({'name':n.name,'code':text},ensure_ascii=True))
  if isinstance(n,ast.ClassDef) and n.name in ('SigninForm','LdapForm'):print(json.dumps({'class':n.name,'fields':ast.unparse(n)},ensure_ascii=True))
for p in base.rglob('*.py'):
 if p.name in ('auths.py','chats.py'):continue
 s=p.read_text(errors='replace')
 if 'internal/identity' in s:
  t=ast.parse(s)
  print(json.dumps({'directory_module':str(p),'routes':[ast.unparse(d) for n in t.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) for d in n.decorator_list if 'router.' in ast.unparse(d)]},ensure_ascii=True))
'''
r=subprocess.run(['docker','exec','-i','ai-server-webui-1','python','-'],input=code,text=True,capture_output=True,timeout=30)
print(r.stdout);print(r.stderr[-500:])
