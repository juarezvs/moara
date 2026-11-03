import subprocess
code="""import json
from pathlib import Path
for p in Path('/app/build/_app/immutable').rglob('*.js.map'):
 try:m=json.loads(p.read_text())
 except Exception:continue
 for name,source in zip(m.get('sources',[]),m.get('sourcesContent',[])):
  if source and name.endswith('/ResponseMessage.svelte'):
   part=source.split('</script>',1)[1];print(part[:5000]);raise SystemExit()
"""
print(subprocess.check_output(['docker','exec','-i','ai-server-webui-1','python','-'],input=code.encode()).decode())
