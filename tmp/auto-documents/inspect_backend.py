import subprocess
code="""from pathlib import Path
s=Path('/app/backend/open_webui/utils/middleware.py').read_text()
for term in ['async def chat_completion_files_handler','async def process_chat_payload','native','files_handler(']:
 start=0
 for _ in range(10):
  at=s.find(term,start)
  if at<0:break
  print('POINT',term,at,'\\n',s[max(0,at-450):at+1700]);start=at+len(term)
"""
print(subprocess.check_output(['docker','exec','-i','ai-server-webui-1','python','-'],input=code.encode()).decode())
