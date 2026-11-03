from pathlib import Path
import json,subprocess,shutil
ROOT=Path('/home/nutec/ai-server')
def run(args):return subprocess.check_output(args,text=True).strip()
assert json.loads((ROOT/'docs/runtime/moara-preservation-latest.json').read_text())['verified']
assert run(['docker','inspect','-f','{{.Image}}','ai-server-webui-1'])=='sha256:6097bff8940e3499eb6a2197426ee9832e72c9e8ca58465cb14f68eecb4472b6'
before={r['Names']:r['ID'] for r in [json.loads(x) for x in run(['docker','ps','--format','{{json .}}']).splitlines()]}
release=ROOT/'docs/runtime/auto-documents-20261027';release.mkdir(mode=0o700,exist_ok=True)
p=ROOT/'moara/infrastructure/chat-feedback-compose.yml';shutil.copy2(p,release/'compose-before.yml')
shutil.copytree('/home/nutec/moara-auto-documents-20261027',ROOT/'moara/webui/auto-documents',dirs_exist_ok=True)
s=p.read_text().replace('image: ai-webui:moara-feedback-20261027','image: ai-webui:moara-auto-documents-20261027').replace('context: ../moara/webui/embedding-retry','context: ../moara/webui/auto-documents').replace('BASE_IMAGE: ai-webui:before-feedback-20261027','BASE_IMAGE: ai-webui:moara-feedback-20261027')
p.write_text(s)
helper=ROOT/'moara/infrastructure/scripts/compose.sh'
try:
 cfg=json.loads(run(['sh',str(helper),'config','--format','json']))
 assert cfg['services']['webui']['environment']['RAG_EMBEDDING_BATCH_SIZE']=='16'
 print(run(['sh',str(helper),'up','-d','--no-deps','--no-build','webui']))
 after={r['Names']:r['ID'] for r in [json.loads(x) for x in run(['docker','ps','--format','{{json .}}']).splitlines()]}
 assert all(after.get(k)==v for k,v in before.items() if k!='ai-server-webui-1')
 print(json.dumps({'published_image':run(['docker','inspect','-f','{{.Image}}','ai-server-webui-1']),'other_services_unchanged':True,'backup_verified':True}))
except Exception:
 shutil.copy2(release/'compose-before.yml',p);raise
