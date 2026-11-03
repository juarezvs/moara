import subprocess
code="""from pathlib import Path
s=Path('/app/backend/open_webui/routers/chats.py').read_text()
for term in ["class ChatForm","async def create_new_chat","async def update_chat_by_id"]:
 i=s.find(term);print(s[max(0,i-100):i+1800])
"""
print(subprocess.check_output(['docker','exec','-i','ai-server-webui-1','python','-'],input=code.encode()).decode())
