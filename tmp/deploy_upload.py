from pathlib import Path
import json,subprocess,shutil,time
root=Path('/home/nutec/ai-server');work=Path('/home/nutec/moara-auto-documents-20261027')
assert json.loads((root/'docs/runtime/moara-preservation-latest.json').read_text())['verified']
backup=root/'docs/runtime/upload-json-20261027';backup.mkdir(parents=True,exist_ok=True)
p=root/'moara/infrastructure/chat-feedback-compose.yml';s=p.read_text()
assert 'image: ai-webui:moara-auto-documents-20261027-r4\n' in s
shutil.copy2(p,backup/'chat-feedback-compose.before.yml')
for filename in ['Dockerfile','install_upload_response.py']:
 target=root/'moara/webui/auto-documents'/filename
 if target.exists():shutil.copy2(target,backup/(filename+'.before'))
 shutil.copy2(work/filename,target)
p.write_text(s.replace('image: ai-webui:moara-auto-documents-20261027-r4\n','image: ai-webui:moara-auto-documents-20261027-r5\n'))
subprocess.run(['sh',str(root/'moara/infrastructure/scripts/compose.sh'),'up','-d','--no-deps','--no-build','webui'],check=True,capture_output=True)
for _ in range(45):
 state=subprocess.check_output(['docker','inspect','-f','{{.State.Health.Status}}','ai-server-webui-1'],text=True).strip()
 if state=='healthy':break
 time.sleep(2)
assert state=='healthy'
print(json.dumps({'health':state,'image':subprocess.check_output(['docker','inspect','-f','{{.Image}}','ai-server-webui-1'],text=True).strip()}))
