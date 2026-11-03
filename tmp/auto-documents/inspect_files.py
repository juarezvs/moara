import subprocess
code="""from pathlib import Path
s=Path('/app/backend/open_webui/utils/middleware.py').read_text()
a=s.index('async def chat_completion_files_handler');b=s.index('\\nasync def ',a+20);print(s[a:b])
for term in ["metadata['files']","form_data.pop('files'","file_context_enabled","files = []"]:
 at=0
 for _ in range(6):
  i=s.find(term,at)
  if i<0:break
  print('POINT',term,s[max(0,i-350):i+600]);at=i+len(term)
"""
print(subprocess.check_output(['docker','exec','-i','ai-server-webui-1','python','-'],input=code.encode()).decode())
