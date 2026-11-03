import subprocess
code="""from pathlib import Path
s=Path('/app/backend/open_webui/utils/middleware.py').read_text()
for term in ["'files': files","metadata.update(","files = [","__files__"]:
 start=s.index("    files = form_data.pop('files', None)")
 for _ in range(5):
  i=s.find(term,start)
  if i<0 or i>117000:break
  print(s[max(0,i-250):i+900]);start=i+len(term)
s=Path('/app/backend/open_webui/tools/builtin.py').read_text();a=s.index('async def _has_read_access_to_file');print(s[a:a+1700])
"""
print(subprocess.check_output(['docker','exec','-i','ai-server-webui-1','python','-'],input=code.encode()).decode())
print(subprocess.check_output(['docker','exec','ai-server-postgres-1','psql','-U','postgres','-d','ai','-Atc',"SELECT display_name, context_length FROM moara.models WHERE active=true"],text=True))
