"""Launch the HTTPS browser test with a short-lived maintenance session on stdin."""
import importlib.util
import io
import json
import subprocess
import tarfile
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
mode=sys.argv[1] if len(sys.argv)>1 else 'core'
if mode not in ('core','sources','governance','native'):raise RuntimeError('Unknown fixed browser test')
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
def run(args,**kwargs):return subprocess.run(args,check=True,capture_output=True,**kwargs)
network=json.loads(run(['docker','inspect','ai-server-caddy-1']).stdout)[0]['NetworkSettings']['Networks']
address=next(v['IPAddress'] for k,v in network.items() if k.endswith('_frontend'))
fixture={'token':module.admin_session(),'caddy_ip':address,'ca_pem':(ROOT/'docs/runtime/ai-root-ca.crt').read_text()}
if mode=='governance':
    fixture['sources']=json.loads((ROOT/'secrets/connector_acceptance_sources.json').read_text())
    fixture['axe_script']=(ROOT/'docs/runtime/axe.min.js').read_text()
    qa=json.loads((ROOT/'secrets/moara_visual_qa.json').read_text())
    fixture['qa_login']={k:qa[k] for k in ('email','password')}
source=(ROOT/('moara/tests/browser_'+mode+'.py' if mode!='core' else 'moara/tests/browser_acceptance.py')).read_bytes()
run(['docker','exec','-i','moara-browser-test','sh','-c','cat > /tmp/moara-core-test.py'],input=source)
result=subprocess.run(['docker','exec','-i','moara-browser-test','python','/tmp/moara-core-test.py'],input=json.dumps(fixture).encode(),capture_output=True,timeout=600 if mode=='sources' else 360)
if result.returncode:
    # Test errors must not contain fixture values or raw page HTML.
    message=result.stderr.decode(errors='replace').replace(fixture['token'],'[REDACTED]')
    for value in fixture.get('qa_login',{}).values():
        if value:message=message.replace(value,'[REDACTED]')
    (ROOT/('docs/runtime/moara-'+mode+'-browser-error.log')).write_text(message)
destination=ROOT/('docs/runtime/moara-'+mode+'-browser');destination.mkdir(exist_ok=True)
archive=run(['docker','exec','moara-browser-test','tar','-C','/tmp/moara-'+mode+'-qa','-cf','-','.']).stdout
with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:bundle.extractall(destination,filter='data')
report=json.loads((destination/'report.json').read_text())
if report['passed']:(ROOT/('docs/runtime/moara-'+mode+'-browser-error.log')).unlink(missing_ok=True)
print(json.dumps({'passed':report['passed'],'checks':report['checks'],'page_errors':report['page_errors'],'failed_assets':report['failed_assets'],'accessibility':report.get('accessibility',{})}))
raise SystemExit(0 if report['passed'] else 1)
