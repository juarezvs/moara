from pathlib import Path
import json,subprocess,shutil,time
root=Path('/home/nutec/ai-server')
assert json.loads((root/'docs/runtime/moara-preservation-latest.json').read_text())['verified']
p=root/'moara/infrastructure/chat-feedback-compose.yml';s=p.read_text()
assert 'image: ai-webui:moara-auto-documents-20261027-r2\n' in s
p.write_text(s.replace('image: ai-webui:moara-auto-documents-20261027-r2\n','image: ai-webui:moara-auto-documents-20261027-r3\n'))
shutil.copy2('/home/nutec/moara-auto-documents-20261027/automatic_documents.py',root/'moara/webui/auto-documents/automatic_documents.py')
subprocess.run(['sh',str(root/'moara/infrastructure/scripts/compose.sh'),'up','-d','--no-deps','--no-build','webui'],check=True,capture_output=True)
for _ in range(45):
 state=subprocess.check_output(['docker','inspect','-f','{{.State.Health.Status}}','ai-server-webui-1'],text=True).strip()
 if state=='healthy':break
 time.sleep(2)
assert state=='healthy'
print(json.dumps({'health':state,'image':subprocess.check_output(['docker','inspect','-f','{{.Image}}','ai-server-webui-1'],text=True).strip()}))
