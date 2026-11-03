import pathlib,importlib.util,subprocess,json
root=pathlib.Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import sys,json,time,urllib.request
token=sys.stdin.readline().strip()
def call(path,body=None):
 request=urllib.request.Request('http://localhost:8075/api/v1/platform'+path,
 data=json.dumps(body).encode() if body is not None else None,
 headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=40) as response:return json.load(response)
queued=call('/runs',{'operation':'agent.run','input':{'agent_id':'legal','query':'Avalie meu caso fictício'}})
for _ in range(30):
 result=call('/runs/'+queued['id'])
 if result['status']=='completed':break
 if result['status']=='failed':raise AssertionError(result.get('error_code'))
 time.sleep(1)
else:raise AssertionError('job timeout')
assert result['result']['legal_verification']['status']=='clarification_required',result
assert result['result']['abstained']
print(json.dumps({'test':'legal_agent_forced_preflight','passed':True,'run_id':queued['id']}))
'''
r=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session()+'\n',capture_output=True,text=True,timeout=70)
print(r.stdout,flush=True)
if r.returncode:print(r.stderr[-1500:]);raise SystemExit(r.returncode)
