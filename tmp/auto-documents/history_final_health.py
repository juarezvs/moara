from pathlib import Path
import json,subprocess
root=Path('/home/nutec/ai-server')
def run(args):return subprocess.check_output(args,text=True).strip()
backup=json.loads((root/'docs/runtime/moara-preservation-latest.json').read_text())
assert backup['verified']
health=run(['docker','inspect','-f','{{.State.Health.Status}}','ai-server-webui-1']);assert health=='healthy'
image=run(['docker','inspect','-f','{{.Image}}','ai-server-webui-1']);assert image=='sha256:eaf105ff83f5b1957c6dce4f544b91adbb59d460b4cd144d61967833d2299985'
before=json.loads((root/'docs/runtime/chat-feedback-20261027/containers-before.json').read_text())
after={r['Names']:r['ID'] for r in [json.loads(x) for x in run(['docker','ps','--format','{{json .}}']).splitlines()]}
assert all(after.get(k)==v for k,v in before.items() if k!='ai-server-webui-1')
code="""import os,hashlib
from pathlib import Path
assert os.environ['RAG_EMBEDDING_BATCH_SIZE']=='16'
print(hashlib.sha256(Path('/app/backend/open_webui/utils/automatic_documents.py').read_bytes()).hexdigest())
"""
source_hash=subprocess.check_output(['docker','exec','-i','ai-server-webui-1','python','-'],input=code.encode()).decode().strip()
print(json.dumps({'health':health,'image':image,'backup_verified':True,'backup_service_result':run(['systemctl','--user','show','ai-backup.service','-p','Result','--value']),'other_services_unchanged':True,'batch_size':16,'automatic_document_module_sha256':source_hash}))
