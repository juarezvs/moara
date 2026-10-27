import json,subprocess,shutil,time
from pathlib import Path
ROOT=Path('/home/nutec/ai-server')
def run(args):return subprocess.check_output(args,text=True).strip()
manifest=ROOT/'docs/runtime/moara-preservation-latest.json'
assert json.loads(manifest.read_text()).get('verified') is True
assert time.time()-manifest.stat().st_mtime<7200,'backup not fresh'
assert run(['docker','inspect','-f','{{.Image}}','ai-server-webui-1'])=='sha256:dc7df15c31cf1affb94039eaad9e4509acf9ae5b690aadd21a80c82aa9b0b624'
before={r['Names']:r['ID'] for r in [json.loads(x) for x in run(['docker','ps','--format','{{json .}}']).splitlines()]}
release=ROOT/'docs/runtime/chat-feedback-20261027';release.mkdir(mode=0o700,exist_ok=True)
helper=ROOT/'moara/infrastructure/scripts/compose.sh'
shutil.copy2(helper,release/'compose-before.sh')
(release/'containers-before.json').write_text(json.dumps(before))
dest=ROOT/'moara/webui/embedding-retry'
shutil.copytree('/home/nutec/moara-chat-feedback-20261027',dest,dirs_exist_ok=True)
overlay=ROOT/'moara/infrastructure/chat-feedback-compose.yml'
assert not overlay.exists() or 'ai-webui:moara-feedback-20261027' in overlay.read_text()
overlay.write_text("services:\n  webui:\n    image: ai-webui:moara-feedback-20261027\n    build:\n      context: ../moara/webui/embedding-retry\n      dockerfile: Dockerfile\n      args:\n        BASE_IMAGE: ai-webui:before-feedback-20261027\n    environment:\n      RAG_EMBEDDING_BATCH_SIZE: '16'\n      RAG_EMBEDDING_CONCURRENT_REQUESTS: '1'\n      ENABLE_ASYNC_EMBEDDING: 'false'\n")
s=helper.read_text();needle=' -f moara/infrastructure/platform-compose.yml "$@"'
assert s.count(needle)==1
helper.write_text(s.replace(needle,' -f moara/infrastructure/platform-compose.yml \\\n -f moara/infrastructure/chat-feedback-compose.yml "$@"'))
try:
 cfg=json.loads(run(['sh',str(helper),'config','--format','json']))
 assert cfg['services']['webui']['image']=='ai-webui:moara-feedback-20261027'
 print(run(['sh',str(helper),'up','-d','--no-deps','--no-build','webui']))
 after={r['Names']:r['ID'] for r in [json.loads(x) for x in run(['docker','ps','--format','{{json .}}']).splitlines()]}
 assert all(after.get(k)==v for k,v in before.items() if k!='ai-server-webui-1'),'another service changed'
 print(json.dumps({'published_image':run(['docker','inspect','-f','{{.Image}}','ai-server-webui-1']),'other_containers_unchanged':True,'backup_verified':True}))
except Exception:
 shutil.copy2(release/'compose-before.sh',helper)
 print('Restored compose helper after deployment failure; candidate state needs inspection.')
 raise
