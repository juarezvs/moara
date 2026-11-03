"""Publish the validated UI without schema, model or inference gateway changes."""
import pathlib,subprocess,json,time
root=pathlib.Path(__file__).resolve().parents[2]
report=json.loads((root/'docs/runtime/workbench-ui.json').read_text())
planning=json.loads((root/'docs/runtime/workbench-plan.json').read_text())
assert report.get('candidate_proxy') and all(report['checks'].values())
assert all(planning['checks'].values())
backup_lines=(root/'tmp/workbench-prepublish-backup.log').read_text().splitlines()
assert any(line.startswith('{') and json.loads(line).get('verified') is True for line in backup_lines),'Backup restoration must pass before publication'
wrapper=root/'moara/infrastructure/scripts/compose.sh';backup=root/'backups/workbench-20261030/compose-before'
backup.parent.mkdir(exist_ok=True)
if not backup.exists():backup.write_bytes(wrapper.read_bytes())
text=wrapper.read_text()
if 'workbench-compose.yml' not in text:
    text=text.replace(' "$@"',' \\\n -f moara/infrastructure/workbench-compose.yml "$@"')
wrapper.write_text(text);wrapper.chmod(0o755)
command=['sh',str(wrapper)]
subprocess.run(command+['config','--quiet'],cwd=root,check=True)
subprocess.run(command+['up','-d','--no-deps','moara-gateway'],cwd=root,check=True)
for _ in range(30):
    process=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c',
        'import urllib.request;print(urllib.request.urlopen("http://localhost:8075/api/v1/ready",timeout=3).status)'],capture_output=True)
    if process.returncode==0:break
    time.sleep(1)
else:raise RuntimeError('Updated UI gateway did not become ready')
print(json.dumps({'published':True,'image':'moara-core:workbench-20261030','ready':True,'database_migration':False,'inference_restarted':False}))
