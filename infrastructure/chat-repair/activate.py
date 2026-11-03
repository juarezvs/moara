import pathlib,subprocess,time,json
root=pathlib.Path(__file__).resolve().parents[2]
report=json.loads((root/'docs/runtime/chat-repair-acceptance-stage.json').read_text());assert report['checks_passed']
assert any(line.startswith('{') and json.loads(line).get('verified') is True for line in (root/'tmp/chat-intent-prepublish-backup.log').read_text().splitlines())
wrapper=root/'moara/infrastructure/scripts/compose.sh';backup=root/'backups/chat-intent-20261030/compose-before';backup.parent.mkdir(exist_ok=True)
if not backup.exists():backup.write_bytes(wrapper.read_bytes())
s=wrapper.read_text()
if 'chat-intent-compose.yml' not in s:s=s.replace(' "$@"',' \\\n -f moara/infrastructure/chat-intent-compose.yml "$@"')
wrapper.write_text(s);wrapper.chmod(0o755)
command=['sh',str(wrapper)]
subprocess.run(command+['config','--quiet'],cwd=root,check=True)
subprocess.run(command+['up','-d','--no-deps','moara-gateway'],cwd=root,check=True)
for _ in range(30):
 p=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c','import urllib.request;urllib.request.urlopen("http://localhost:8075/api/v1/ready",timeout=3)'],capture_output=True)
 if p.returncode==0:break
 time.sleep(1)
else:raise RuntimeError('Corrected gateway not ready')
subprocess.run(['python3',str(root/'infrastructure/chat-repair/update_retrieval_template.py')],check=True)
print('CHAT_INTENT_AND_CONTEXT_CORRECTION_PUBLISHED')
