"""Build the quota fix over the exact running image, without changing services."""
import json
import pathlib
import subprocess

root = pathlib.Path('/home/nutec/ai-server')
folder = root / 'tmp/continue-unlimited-20261102'
folder.mkdir(parents=True, exist_ok=True)
container = 'ai-server-moara-gateway-1'
original = json.loads(subprocess.check_output(['docker', 'inspect', container]))[0]
for name in ['auth.py', 'admin_api.py']:
    subprocess.run(['docker', 'cp', container + ':/app/moara/gateway/' + name,
                    str(folder / (name + '.before'))], check=True)
auth = (folder / 'auth.py.before').read_text()
old = "        await self.limit('actor:'+actor.subject+(':'+str(actor.key_id) if actor.key_id else ''),rate,60)"
assert auth.count(old) == 1
auth = auth.replace(old, "        # rpm=0 is an administrative per-key exemption; auth and scopes still apply.\n"
                        "        if not (actor.key_id is not None and rate == 0):\n    " + old)
(folder / 'auth.py').write_text(auth)
admin = (folder / 'admin_api.py.before').read_text()
old = 'rpm:int=Field(default=60,ge=1,le=600)'
assert admin.count(old) == 1
(folder / 'admin_api.py').write_text(admin.replace(old, "rpm:int=Field(default=60,ge=0,le=600,description='0 disables the per-key request quota')"))
base_tag = 'moara-core:pre-continue-unlimited-20261102'
subprocess.run(['docker', 'tag', original['Image'], base_tag], check=True)
(folder / 'Dockerfile').write_text('FROM ' + base_tag + '\nCOPY auth.py admin_api.py /app/moara/gateway/\n'
    'COPY 010_api_key_unlimited_rpm.sql /app/moara/gateway/migrations/\n'
    'COPY 0010_api_key_unlimited_rpm.py /app/moara/gateway/alembic/versions/\n')
tag = 'moara-core:continue-unlimited-20261102'
subprocess.run(['docker', 'build', '--network', 'none', '-t', tag, str(folder)], check=True)
tests = folder / 'tests'
result = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--read-only',
                         '--tmpfs', '/tmp:size=64m', '--cap-drop', 'ALL',
                         '-v', str(tests) + ':/tests:ro', '--entrypoint', 'python', tag,
                         '-m', 'unittest', 'discover', '-s', '/tests', '-v'], capture_output=True, text=True)
print(result.stdout + result.stderr, flush=True)
result.check_returncode()
state = {'base_image': original['Image'], 'image': tag, 'tests_passed': True,
         'container_ids': {x['Names']: x['ID'] for x in map(json.loads, subprocess.check_output(
             ['docker', 'ps', '--format', '{{json .}}'], text=True).splitlines())}}
(folder / 'stage.json').write_text(json.dumps(state, indent=2))
print(json.dumps({'candidate_built': True, 'tests_passed': True, 'production_changed': False}))
