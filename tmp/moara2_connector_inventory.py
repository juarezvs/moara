import pathlib,importlib.util,subprocess
root=pathlib.Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import sys,json,urllib.request
token=sys.stdin.readline().strip()
request=urllib.request.Request('http://localhost:8075/api/v1/connectors/sources',headers={'Authorization':'Bearer '+token})
with urllib.request.urlopen(request,timeout=40) as response:payload=json.load(response)
rows=payload if isinstance(payload,list) else payload.get('sources',payload.get('items',[]))
print(json.dumps({'source_count':len(rows),'active_count':sum(bool(r.get('active')) for r in rows),'pje_sei_candidates':[{'name':r.get('name'),'kind':r.get('kind'),'active':r.get('active')} for r in rows if __import__('re').search(r'\b(?:pje|sei)\b',r.get('name',''),__import__('re').I)]},ensure_ascii=True))
'''
r=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session()+'\n',capture_output=True,text=True,timeout=60)
print(r.stdout,flush=True)
if r.returncode:print(r.stderr[-1000:]);raise SystemExit(r.returncode)
