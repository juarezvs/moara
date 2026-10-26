"""Read-only final production gate; no credentials or request content in output."""
import datetime
import importlib.util
import json
import ipaddress
import ssl
import subprocess
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
checks={};images={};bad=[];running=0;completed=[]
def output(args):return subprocess.check_output(args,text=True).strip()
ids=output(['docker','ps','-aq','--filter','label=com.docker.compose.project=ai-server']).split()
services=json.loads(output(['docker','inspect',*ids]))
for value in services:
    name=value['Name'].lstrip('/');state=value['State'];images[name]=value['Image']
    if state['Status']=='running':
        running+=1
        if state.get('Health',{}).get('Status') in ('unhealthy','starting'):bad.append(name)
    elif state['Status']=='exited' and state['ExitCode']==0 and 'provision' in name:completed.append(name)
    else:bad.append(name)
checks['expected_services_running']=not bad
checks['no_test_containers']=all(not output(['docker','ps','-aq','--filter','label='+label]) for label in
    ['moara.environment=staging','com.docker.compose.project=cc-fixtures','moara.test=directory','moara.test=native-browser'])
checks['no_test_containers']=checks['no_test_containers'] and not output(['docker','ps','-aq','--filter','label=moara.test'])
checks['private_ports_only']=all(not value['HostConfig'].get('PortBindings') or all(
    binding.get('HostIp')=='127.0.0.1' and binding.get('HostPort') in ('8443','8080')
    for entries in value['HostConfig']['PortBindings'].values() for binding in entries) for value in services)
checks['backup_restore_verified']=all(json.loads((ROOT/'docs/runtime'/name).read_text())['verified'] for name in
    ['moara-preservation-latest.json','moara-preservation-restore.json'])
checks['user_services_start_on_boot']=all(output(['systemctl','--user','is-enabled',unit])=='enabled' for unit in
    ['docker.service','moara-host-telemetry.service']) and output(['loginctl','show-user','nutec','-p','Linger','--value'])=='yes'
checks['applied_migration_is_0004']=output(['docker','exec','ai-server-postgres-1','psql','-U','postgres','-d','ai','-At',
    '-c','SELECT version_num FROM moara.alembic_version'])=='0004_connector_tickets'
worker_probe="from redis import Redis;from moara.gateway.settings import secret;r=Redis(host='moara-redis',password=secret('moara_redis_password'),db=1,socket_timeout=3);print('READY' if r.exists('moara:worker:presence') else 'NOT_READY')"
checks['administrative_worker_heartbeat']=output(['docker','exec','ai-server-moara-worker-1','python','-c',worker_probe])=='READY'
checks['public_sockets_persist_on_boot']=all(output(['systemctl','is-enabled',name])=='enabled' and output(['systemctl','is-active',name])=='active' for name in ['moara-http.socket','moara-https.socket'])
networks=json.loads(output(['docker','network','inspect',*output(['docker','network','ls','-q']).split()]))
checks['docker_does_not_shadow_sectional_networks']=all(not ipaddress.ip_network(item['Subnet']).overlaps(ipaddress.ip_network('172.16.0.0/12')) for net in networks for item in net['IPAM'].get('Config') or [])
corporate_context=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/moara-domain-root-ca.crt'))
for path in ['/','/api/config','/moara/api/v1/ready','/studio/']:
    with urllib.request.urlopen('https://moara.am.trf1.gov.br'+path,context=corporate_context,timeout=20) as response:checks['corporate_https:'+path]=response.status==200
context=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/ai-root-ca.crt'))
for path in ['/moara/api/v1/ready','/moara/','/','/studio/','/sobre']:
    with urllib.request.urlopen('https://localhost:8443'+path,context=context,timeout=20) as response:checks['https:'+path]=response.status==200
# Exercise the native provider client as well: HTTP health alone cannot detect
# a retained upstream connection/DNS entry after gateway replacement. Identity
# is a canonical answer, so this probe creates no chat history or LLM workload.
try:
    spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py')
    maintenance=importlib.util.module_from_spec(spec);spec.loader.exec_module(maintenance)
    token=maintenance.admin_session()
    request=urllib.request.Request('https://moara.am.trf1.gov.br/openai/chat/completions',
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},
        data=json.dumps({'model':'auto','messages':[{'role':'user','content':'Quem é você?'}],'stream':False}).encode())
    with urllib.request.urlopen(request,context=corporate_context,timeout=30) as response:value=json.load(response)
    checks['native_chat_provider_operational']='Moara' in value['choices'][0]['message']['content'] and value.get('moara',{}).get('inference_used') is False
except Exception:checks['native_chat_provider_operational']=False
report={'passed':all(checks.values()),'checks':checks,'running_services':running,'completed_provisioners':completed,
    'unhealthy_services':bad,'image_ids':images,'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'scope':'real production services, migration, verified recovery and TLS; no synthetic test containers remain'}
(ROOT/'docs/runtime/moara-final-health.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='image_ids'}));raise SystemExit(0 if report['passed'] else 1)
