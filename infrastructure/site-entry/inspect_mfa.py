import subprocess
code=r'''
import pathlib,ast,json
p=pathlib.Path('/app/backend/open_webui/routers/mfa.py');s=p.read_text();t=ast.parse(s)
for n in t.body:
 if isinstance(n,ast.ClassDef) and (n.name=='MfaRoute' or n.name.endswith('Form')):
  print(json.dumps({'name':n.name,'code':ast.unparse(n)[:11000]},ensure_ascii=True))
 if isinstance(n,(ast.AsyncFunctionDef,ast.FunctionDef)):
  routes=[ast.unparse(d) for d in n.decorator_list if 'router.' in ast.unparse(d)]
  if routes:print(json.dumps({'name':n.name,'routes':routes,'args':ast.unparse(n.args)},ensure_ascii=True))
'''
r=subprocess.run(['docker','exec','-i','ai-server-webui-1','python','-'],input=code,text=True,capture_output=True,timeout=20)
print(r.stdout);print(r.stderr[-500:])
