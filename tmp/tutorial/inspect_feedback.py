import subprocess,json
from pathlib import Path
code="""import inspect
from pathlib import Path
s=Path('/app/backend/open_webui/retrieval/utils.py').read_text();at=s.index('async def agenerate_openai_batch_embeddings');print(s[at:at+500])
s=Path('/app/backend/open_webui/tools/builtin.py').read_text();at=s.index('async def view_file');print(s[at:at+2200])
s=Path('/app/backend/open_webui/config.py').read_text()
for line in s.splitlines():
 if 'RAG_EMBEDDING_TIMEOUT' in line:print(line)
"""
print(subprocess.check_output(['docker','exec','-i','ai-server-webui-1','python','-'],input=code.encode()).decode())
p=Path('/home/nutec/ai-server/docs/runtime/moara-preservation-latest.json');d=json.loads(p.read_text());print('backup', {k:v for k,v in d.items() if k in ['verified','timestamp','created_at']})
print(Path('/home/nutec/ai-server/moara/infrastructure/scripts/compose.sh').read_text())
