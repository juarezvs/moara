import subprocess
code="""from pathlib import Path
s=Path('/app/backend/open_webui/utils/middleware.py').read_text()
for term in ['async def apply_source_context_to_messages','async def process_chat_payload']:
 a=s.find(term)
 if a>=0:print(s[a:a+3500] if 'apply_' in term else '')
s=Path('/app/backend/open_webui/routers/retrieval.py').read_text()
a=s.find('docs = await loader.aload');print(s[a-900:a+1500])
"""
print(subprocess.check_output(['docker','exec','-i','ai-server-webui-1','python','-'],input=code.encode()).decode())
