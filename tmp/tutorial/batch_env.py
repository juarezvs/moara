import subprocess
code="""from pathlib import Path
for f in ['config.py','env.py']:
 lines=(Path('/app/backend/open_webui')/f).read_text().splitlines()
 for i,line in enumerate(lines):
  if any(x in line for x in ['RAG_EMBEDDING_BATCH_SIZE =','RAG_EMBEDDING_CONCURRENT_REQUESTS =','ENABLE_PERSISTENT_CONFIG =','RAG_EMBEDDING_TIMEOUT =']):
   print(f,'\\n'.join(lines[i:i+9]))
"""
print(subprocess.check_output(['docker','exec','-i','ai-server-webui-1','python','-'],input=code.encode()).decode())
