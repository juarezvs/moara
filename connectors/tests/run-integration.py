"""Run only against verified fixture containers, keeping credentials on stdin."""
import json
import subprocess
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
for kind in ['postgres','mysql','oracle','mssql','mongodb','sqlite','rest','hub']:
    deadline=time.monotonic()+60
    while True:
        value=json.loads(subprocess.check_output(['docker','inspect','ai-server-connector-'+kind+'-1']))[0]
        if value['State'].get('Health',{}).get('Status')=='healthy':break
        if time.monotonic()>deadline:raise RuntimeError('Connector readiness timed out: '+kind)
        time.sleep(1)
for name in ['pg','mysql','mariadb','mssql','oracle','mongodb','rest']:
    value=json.loads(subprocess.check_output(['docker','inspect','cc-fixture-'+name]))[0]
    assert value['Config']['Labels'].get('curumim.fixtures')=='true'
    assert value['Config']['Labels'].get('com.docker.compose.project')=='cc-fixtures'
    assert not value['HostConfig'].get('PortBindings') and value['State']['Running']
credentials=json.loads((ROOT/'secrets/connector_fixture_credentials.json').read_text())
state=ROOT/'secrets/connector_acceptance_sources.json'
if state.exists():credentials['sources']=json.loads(state.read_text())
source=(ROOT/'connectors/tests/integration.py').read_bytes()
subprocess.run(['docker','exec','-i','ai-server-connector-hub-1','sh','-c','cat > /tmp/connector-integration.py'],input=source,check=True)
result=subprocess.run(['docker','exec','-i','ai-server-connector-hub-1','python','/tmp/connector-integration.py'],input=json.dumps(credentials).encode(),capture_output=True,timeout=600)
if not result.stdout:
    (ROOT/'secrets/connector-integration-error.log').write_bytes(result.stderr)
    raise RuntimeError('Connector acceptance failed before producing a report; private diagnostic retained')
report=json.loads(result.stdout)
state.write_text(json.dumps(report['sources']));state.chmod(0o600)
(ROOT/'docs/runtime/connector-integration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'passed':report['passed'],'checks':len(report['checks']),'failures':report['failures']}))
raise SystemExit(0 if report['passed'] else 1)
