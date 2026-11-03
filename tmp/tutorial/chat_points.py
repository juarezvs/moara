import subprocess
code="""import json
from pathlib import Path
for p in Path('/app/build/_app/immutable').rglob('*.js.map'):
 try:m=json.loads(p.read_text())
 except Exception:continue
 for name,s in zip(m.get('sources',[]),m.get('sourcesContent',[])):
  if s and (name.endswith('/Chat.svelte') or name.endswith('/apis/files/index.ts')):
   for term in ['chat:completion','chat:tasks:cancel','uploadFile','event.data','data.done']:
    at=s.find(term)
    if at>=0:print(name,term,s[max(0,at-250):at+1900])
"""
print(subprocess.check_output(['docker','exec','-i','ai-server-webui-1','python','-'],input=code.encode()).decode())
