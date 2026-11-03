from pathlib import Path
import subprocess,json,time
ROOT=Path('/home/nutec/ai-server')
p=ROOT/'moara/infrastructure/chat-feedback-compose.yml'
s=p.read_text()
if 'environment:' not in s:p.write_text(s+"    environment:\n      RAG_EMBEDDING_BATCH_SIZE: '16'\n      RAG_EMBEDDING_CONCURRENT_REQUESTS: '1'\n      ENABLE_ASYNC_EMBEDDING: 'false'\n")
r=json.loads((ROOT/'docs/runtime/embedding-upload-validation-20261027.json').read_text());identifier=r['file_id']
code="""import asyncio,os
from pathlib import Path
for entry in Path('/proc/1/environ').read_bytes().split(b'\\0'):
 if entry.startswith(b'WEBUI_SECRET_KEY='):os.environ['WEBUI_SECRET_KEY']=entry.split(b'=',1)[1].decode()
from open_webui.models.files import Files
async def main():
 f=await Files.get_file_by_id(%r)
 assert f and f.filename.startswith('moara-validacao-embedding-')
 await Files.update_file_data_by_id(f.id,{'status':'failed','error':'synthetic_validation_restarted_for_persistent_batch_config'})
 print('Synthetic validation marked for cleanup.')
asyncio.run(main())
"""%identifier
result=subprocess.run(['docker','exec','-i','ai-server-webui-1','python','-'],input=code.encode(),capture_output=True,timeout=60)
assert result.returncode==0,result.stderr.decode()[-500:]
print('Only owned synthetic validation marked failed; test runner will clean it.')
time.sleep(7)
subprocess.run(['sh',str(ROOT/'moara/infrastructure/scripts/compose.sh'),'up','-d','--no-deps','--no-build','webui'],check=True,capture_output=True)
for _ in range(40):
 state=subprocess.check_output(['docker','inspect','-f','{{.State.Health.Status}}','ai-server-webui-1'],text=True).strip()
 if state=='healthy':break
 time.sleep(2)
assert state=='healthy'
print('WebUI healthy with deployment-level batch size 16.')
