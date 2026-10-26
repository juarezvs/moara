import importlib.util,json,ssl,subprocess,urllib.request,urllib.error
from pathlib import Path
ROOT=Path('/home/nutec/ai-server')
def run(args):return subprocess.check_output(args,text=True).strip()
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
token=module.admin_session();tls=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/moara-domain-root-ca.crt'))
checks={}
for path in ('/moara/api/v1/platform/agents','/moara/api/v1/platform/groups','/moara/api/v1/platform/runs'):
 req=urllib.request.Request('https://moara.am.trf1.gov.br'+path,headers={'Authorization':'Bearer '+token})
 with urllib.request.urlopen(req,context=tls,timeout=20) as response:
  checks[path]=response.status;response.read()
states={}
for unit in ('ai-server.service','moara-sandbox-worker.service'):
 states[unit]=run(['systemctl','--user','is-active',unit])
containers=[]
for name in run(['docker','ps','--format','{{.Names}}']).splitlines():
 if not name.startswith('ai-server-'):continue
 obj=json.loads(run(['docker','inspect',name]))[0]
 containers.append({'name':name,'status':obj['State']['Status'],'health':obj['State'].get('Health',{}).get('Status')})
schema=run(['docker','exec','ai-server-postgres-1','psql','-U','postgres','-d','ai','-Atc','SELECT version_num FROM moara.alembic_version'])
checks['migration_0005']=schema=='0005_platform'
assert all(c['status']=='running' and c['health'] in (None,'healthy') for c in containers)
assert all(v==200 or v is True for v in checks.values())
print(json.dumps({'checks':checks,'services':states,'containers':containers,'institutional_content_returned':False}))
