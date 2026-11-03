import pathlib,subprocess,importlib.util
root=pathlib.Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import sys,json,urllib.request
token=sys.stdin.read().strip()
request=urllib.request.Request('http://localhost:8075/api/v1/models/profiles',headers={'Authorization':'Bearer '+token})
with urllib.request.urlopen(request) as r:rows=json.load(r)
print(json.dumps([{'id':row['id'],'settings':{key:row.get('settings',{}).get(key) for key in ['context_length','max_tokens','timeout']}} for row in rows if row['id'] in ['general','fast','gemma4-12b']]))
'''
p=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session(),capture_output=True,text=True,timeout=30)
if p.returncode:raise RuntimeError(p.stderr[-1000:])
print(p.stdout)
