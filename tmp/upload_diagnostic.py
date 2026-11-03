import subprocess,json
from pathlib import Path
ROOT=Path('/home/nutec/ai-server')
for p in (ROOT/'infrastructure').rglob('*Caddy*'):
 if p.is_file():
  lines=p.read_text(errors='replace').splitlines()
  for i,line in enumerate(lines):
   if any(x in line for x in ['max_size','request_body','body_size','handle_errors']):
    print(str(p.relative_to(ROOT)),i+1,'\n'.join(lines[max(0,i-2):i+5]))
logs=subprocess.check_output(['docker','logs','--since','2h','ai-server-caddy-1'],stderr=subprocess.STDOUT).decode(errors='replace')
rows=[]
for line in logs.splitlines():
 try:r=json.loads(line)
 except:continue
 req=r.get('request') or {};uri=req.get('uri','')
 if '/api/v1/files' in uri and r.get('status',0)>=400:
  rows.append({k:r.get(k) for k in ['status','size','duration','msg']}|{'method':req.get('method'),'route':uri.split('?')[0]})
print(json.dumps({'upload_errors':rows[-12:]}))
