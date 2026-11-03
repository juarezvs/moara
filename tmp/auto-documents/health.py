import subprocess
code="""import ast
from pathlib import Path
s=ast.parse(Path('/app/backend/open_webui/utils/misc.py').read_text())
names={x.name for x in s.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))}
print({'imports_present':all(x in names for x in ['get_last_user_message','add_or_update_system_message'])})
"""
print(subprocess.check_output(['docker','exec','-i','ai-server-webui-1','python','-'],input=code.encode()).decode())
print(subprocess.check_output(['docker','inspect','-f','{{.State.Health.Status}}','ai-server-webui-1'],text=True))
