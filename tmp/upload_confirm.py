import subprocess,json,urllib.request,urllib.error,ssl
from pathlib import Path
ROOT=Path('/home/nutec/ai-server')
raw=subprocess.check_output(['docker','inspect','ai-server-caddy-1'])
obj=json.loads(raw)[0]
print(json.dumps({'caddy_mounts':[{'source':x['Source'],'destination':x['Destination']} for x in obj['Mounts']]}))
ctx=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/moara-domain-root-ca.crt'))
req=urllib.request.Request('https://moara.am.trf1.gov.br/api/v1/files/',data=b'x'*11868084,method='POST',headers={'Content-Type':'application/octet-stream'})
try:
 with urllib.request.urlopen(req,context=ctx,timeout=45) as r:print({'status':r.status,'bytes':len(r.read())})
except urllib.error.HTTPError as e:
 body=e.read();print({'status':e.code,'response_bytes':len(body),'content_type':e.headers.get('Content-Type')})
except Exception as e:print({'connection_error':type(e).__name__})
code="""from pathlib import Path
s=Path('/app/backend/open_webui/routers/files.py').read_text().splitlines()
for i,line in enumerate(s):
 if any(x in line for x in ['max_size','max_file','MAX_SIZE']):
  print('\\n'.join(s[max(0,i-2):i+4]))
"""
print(subprocess.check_output(['docker','exec','-i','ai-server-webui-1','python','-'],input=code.encode()).decode())
