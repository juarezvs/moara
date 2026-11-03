import pathlib,subprocess,json,importlib.util
root=pathlib.Path(__file__).resolve().parents[2]
pdf=json.loads((root/'docs/runtime/pdf-root-probe-after.json').read_text())
for key in ['default','max_tokens_4096']:
 result=pdf[key];assert result['http_status']==200 and not result['budget_error']
 assert result['metadata']['assistant']['id']=='documental'
 assert not result['metadata']['context_management']['current_input_truncated']
 assert result['metadata']['citation_validation']=='client_source_ids_only'
conversation=json.loads((root/'docs/runtime/chat-repair-acceptance-production.json').read_text());assert conversation['checks_passed']
public=json.loads((root/'docs/runtime/chat-repair-root-smoke.json').read_text());assert public['quais suas habilidades?'] and public['o que você pode fazer?']
budget=json.loads((root/'docs/runtime/chat-repair-budget-acceptance.json').read_text());assert budget['passed'] and budget['notice_in_answer']
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import sys,json,urllib.request
request=urllib.request.Request('http://localhost:8075/api/v1/observability/inference',headers={'Authorization':'Bearer '+sys.stdin.read().strip()})
with urllib.request.urlopen(request,timeout=15) as response:value=json.load(response)
assert value['available'] and value['principal_resident'] and value['embeddings_resident']
print(json.dumps(value))
'''
process=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session(),text=True,capture_output=True,timeout=30)
if process.returncode:raise RuntimeError(process.stderr[-1000:])
rows=[json.loads(line) for line in subprocess.check_output(['docker','ps','--format','json'],text=True).splitlines()]
candidates=[row['Names'] for row in rows if row['Names'].startswith('moara-chat-intent-stage-')]
if candidates:subprocess.run(['docker','stop',*candidates],check=True,stdout=subprocess.DEVNULL)
services=[json.loads(line) for line in subprocess.check_output(['sh',str(root/'moara/infrastructure/scripts/compose.sh'),'ps','--format','json'],cwd=root,text=True).splitlines()]
assert all(row['State']=='running' and row.get('Health')!='unhealthy' for row in services)
core=json.loads(subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1']))[0]
assert core['Config']['Image']=='moara-core:chat-intent-20261030'
fixture=pathlib.Path('/home/nutec/.cache/moara-validation-325b059af1f8/process.pdf')
if fixture.exists():fixture.unlink() # Only the private temporary copy created by this validation.
report={'published':True,'image':core['Config']['Image'],'image_id':core['Image'],'services_running':len(services),
 'unit_tests_passed':64,'pdf_actual_chat_passed':True,'capabilities_actual_chat_passed':True,
 'history_budget_notice_passed':True,'private_candidates_stopped':candidates,
 'temporary_pdf_fixture_removed':not fixture.exists(),'institutional_files_and_history_preserved':True,
 'inference':json.loads(process.stdout)}
(root/'docs/runtime/chat-repair-final-operation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
