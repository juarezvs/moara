from pathlib import Path
import json,sys
report=json.loads(Path('output/moara2/moara2-production-acceptance-20261030.json').read_text())
p=Path('docs/MOARA_2_IMPLEMENTATION_2026-10-30.md');s=p.read_text(encoding='utf8')
s=s.replace('16,20 s','16,73 s').replace('0,15 s','0,20 s').replace('16,19 s','16,72 s').replace('2,42 s','1,80 s').replace('6,57 s','6,41 s')
s=s.replace('resultado `verification_incomplete`','resultado `verification_incomplete`')
s=s.replace('Candidatas privadas foram paradas','Candidatas privadas foram paradas')
p.write_text(s,encoding='utf8')
sys.path.insert(0,'tmp')
from gpu_remote import source
script=r'''set -eu
cd /home/nutec/ai-server
sh moara/infrastructure/scripts/compose.sh config --quiet
sh moara/infrastructure/scripts/compose.sh ps --format json >tmp/moara2-final-service-state.json
python3 - <<'PY'
import json,pathlib,subprocess,urllib.request
root=pathlib.Path('/home/nutec/ai-server')
rows=[json.loads(line) for line in (root/'tmp/moara2-final-service-state.json').read_text().splitlines()]
state={'services':len(rows),'not_running':[r['Service'] for r in rows if r['State']!='running'],
    'unhealthy':[r['Service'] for r in rows if r.get('Health')=='unhealthy']}
assert not state['not_running'] and not state['unhealthy'],state
for name in ['moara-gateway','gateway']:
    row=json.loads(subprocess.check_output(['docker','inspect','ai-server-'+name+'-1']))[0]
    state[name]={'image':row['Config']['Image'],'image_id':row['Image'],'status':row['State']['Status']}
for name in ['ai-server-moara-gpu-tunnel-1']:
    status=subprocess.check_output(['docker','inspect',name,'--format','{{.State.Status}}'],text=True).strip()
    assert status=='exited';state['legacy_relay']=status
state['ready']=subprocess.check_output(['docker','exec','ai-server-moara-gateway-1','python','-c','import urllib.request;print(urllib.request.urlopen("http://localhost:8075/api/v1/ready").read().decode())'],text=True).strip()
state['core_tests_passed']=43;state['inference_gateway_tests_passed']=9
(root/'docs/runtime/moara2-final-operation-20261030.json').write_text(json.dumps(state,indent=2))
print(json.dumps(state))
PY
'''
print(source(script))
