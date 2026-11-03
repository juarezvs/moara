import pathlib,subprocess,json
ROOT=pathlib.Path('/home/nutec/ai-server');core=(ROOT/'tmp/unified-core-name.txt').read_text().strip();proxy=(ROOT/'tmp/unified-proxy-name.txt').read_text().strip()
code=r'''
import httpx,re,json,sys
from pathlib import Path
for base in ['http://localhost:8075','http://'+sys.argv[1]+':8080','http://moara-gateway:8075']:
 r=httpx.get(base+'/moara/login',trust_env=False,timeout=10);scripts=re.findall(r'<script[^>]*src="([^"]+)"',r.text)
 print(json.dumps({'base':base,'status':r.status_code,'scripts':scripts}))
 if scripts:
  data=httpx.get(base+'/moara/'+scripts[-1],trust_env=False,timeout=10).text
  print(json.dumps({'contains_native_mfa':'mfa-code' in data,'contains_context':'context-expanded' in data,'bytes':len(data)}))
'''
r=subprocess.run(['docker','exec','-i',core,'python','-',proxy],input=code,text=True,capture_output=True,timeout=55)
print(r.stdout);print(r.stderr[-500:])
print((ROOT/'tmp/unified-proxy/Caddyfile-stage').read_text().split('handle /moara/*')[1][:240])
