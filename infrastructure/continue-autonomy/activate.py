"""Publish the tested quota implementation and exempt exactly one existing key."""
import json
import pathlib
import re
import subprocess
import sys
import time

root = pathlib.Path('/home/nutec/ai-server')
folder = root / 'tmp/continue-unlimited-20261102'
state = json.loads((folder / 'stage.json').read_text())
key_hash = sys.argv[1]
assert re.fullmatch('[0-9a-f]{64}', key_hash)
assert state['tests_passed']
wrapper = root / 'moara/infrastructure/scripts/compose.sh'
before = wrapper.read_bytes()
(folder / 'compose.before').write_bytes(before)
assert json.loads(subprocess.check_output(['docker', 'inspect', 'ai-server-moara-gateway-1']))[0]['Image'] == state['base_image']


def sql(value):
    return subprocess.check_output(['docker', 'exec', '-i', 'ai-server-postgres-1', 'psql',
                                    '-X', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', 'ai', '-At'],
                                   input=value, text=True).strip()


key = json.loads(sql("SELECT row_to_json(k) FROM (SELECT id,rpm FROM moara.api_keys WHERE token_hash='" + key_hash +
                    "' AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at>now())) k;"))
(folder / 'key.before.json').write_text(json.dumps(key))
assert sql('SELECT version_num FROM moara.alembic_version;') == '0009_chat_assistant_context'
(folder / 'constraint.before.txt').write_text(sql("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='moara.api_keys'::regclass AND conname='api_keys_rpm_check';"))
overlay = root / 'moara/infrastructure/continue-unlimited-compose.yml'
assert not overlay.exists() or overlay.read_text() == 'services:\n  moara-gateway:\n    image: ' + state['image'] + '\n'
overlay.write_text('services:\n  moara-gateway:\n    image: ' + state['image'] + '\n')


def up():
    subprocess.run(['sh', str(wrapper), 'config', '--quiet'], cwd=root, check=True)
    subprocess.run(['sh', str(wrapper), 'up', '-d', '--no-deps', '--no-build', 'moara-gateway'], cwd=root, check=True)
    for _ in range(40):
        result = subprocess.run(['docker', 'exec', 'ai-server-moara-gateway-1', 'python', '-c',
            "import urllib.request;assert urllib.request.urlopen('http://localhost:8075/api/v1/ready',timeout=3).status==200"], capture_output=True)
        if not result.returncode:
            return
        time.sleep(1)
    raise RuntimeError('Gateway readiness failed')


changed_db = False
try:
    assert before.decode().count(' "$@"') == 1
    wrapper.write_text(before.decode().replace(' "$@"', ' \\\n -f moara/infrastructure/continue-unlimited-compose.yml "$@"'))
    wrapper.chmod(0o755)
    up()
    migration = (folder / '010_api_key_unlimited_rpm.sql').read_text()
    sql("BEGIN;\n" + migration + "\nUPDATE moara.alembic_version SET version_num='0010_api_key_unlimited_rpm' WHERE version_num='0009_chat_assistant_context';\n"
        "UPDATE moara.api_keys SET rpm=0 WHERE id='" + key['id'] + "';\n"
        "INSERT INTO moara.audit(actor_subject,action,resource,status) VALUES('operator:continue-configuration','api_key.rate_limit.disabled','" + key['id'] + "','ok');\nCOMMIT;")
    changed_db = True
    assert sql("SELECT rpm FROM moara.api_keys WHERE id='" + key['id'] + "';") == '0'
    after = {x['Names']: x['ID'] for x in map(json.loads, subprocess.check_output(
        ['docker', 'ps', '--format', '{{json .}}'], text=True).splitlines())}
    assert all(after.get(k) == v for k, v in state['container_ids'].items() if k != 'ai-server-moara-gateway-1')
    report = {'published': True, 'key_id': key['id'], 'previous_rpm': key['rpm'], 'rpm': 0,
              'quota_disabled': True, 'other_containers_unchanged': True, 'image': state['image']}
    (folder / 'activated.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
except Exception:
    if changed_db:
        sql("UPDATE moara.api_keys SET rpm=" + str(key['rpm']) + " WHERE id='" + key['id'] + "';")
    wrapper.write_bytes(before)
    wrapper.chmod(0o755)
    up()
    raise
