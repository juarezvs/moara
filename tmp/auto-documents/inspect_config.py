import subprocess,importlib.util,json,ssl,urllib.request
from pathlib import Path
ROOT=Path('/home/nutec/ai-server')
code="""from pathlib import Path
s=Path('/app/backend/open_webui/utils/middleware.py').read_text()
a=s.index("    files = form_data.pop('files', None)")
print(s[a+1800:a+5600])
"""
print(subprocess.check_output(['docker','exec','-i','ai-server-webui-1','python','-'],input=code.encode()).decode())
spec=importlib.util.spec_from_file_location('m',ROOT/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
token=m.admin_session();ctx=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/moara-domain-root-ca.crt'))
req=urllib.request.Request('https://moara.am.trf1.gov.br/api/models',headers={'Authorization':'Bearer '+token})
with urllib.request.urlopen(req,context=ctx,timeout=30) as r:d=json.load(r)
print(json.dumps([{'id':x.get('id'),'capabilities':x.get('info',{}).get('meta',{}).get('capabilities'),'params':x.get('info',{}).get('params')} for x in d.get('data',[])],ensure_ascii=False))
