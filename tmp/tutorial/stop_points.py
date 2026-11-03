import subprocess
code="""import json
from pathlib import Path
found=set()
for p in Path('/app/build/_app/immutable').rglob('*.js.map'):
 try:m=json.loads(p.read_text())
 except Exception:continue
 for name,source in zip(m.get('sources',[]),m.get('sourcesContent',[])):
  if not source or name in found:continue
  if any(key in name for key in ['chat/MessageInput.svelte']):
   found.add(name);print('SOURCE '+name)
   lines=source.splitlines()
   matches=[i for i,line in enumerate(lines) if any(key in line for key in ['Stop','stopResponse'])]
   for i in matches[-8:]:print('\\n'.join(lines[max(0,i-4):i+12]))
"""
p=subprocess.run(['docker','exec','-i','ai-server-webui-1','python','-'],input=code.encode(),capture_output=True,timeout=60)
print(p.stdout.decode()[:16000])
