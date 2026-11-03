import re,subprocess
from pathlib import Path
p=Path('docs/evidence/chat-feedback-browser-production.txt')
s=p.read_text(encoding='utf-8');tokens=set(re.findall(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',s))
for token in tokens:
 code="""import urllib.request,ssl
ctx=ssl.create_default_context(cafile='/home/nutec/ai-server/docs/runtime/moara-domain-root-ca.crt')
req=urllib.request.Request('https://moara.am.trf1.gov.br/api/v1/auths/signout',data=b'{}',headers={'Authorization':'Bearer '+%r,'Content-Type':'application/json'})
with urllib.request.urlopen(req,context=ctx,timeout=30) as r:print('Temporary test session revoked:',r.status)
"""%token
 r=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','nutec@172.19.5.250','python3 -'],input=code.encode(),capture_output=True)
 assert r.returncode==0,'session revocation failed'
 print(r.stdout.decode().strip())
 s=s.replace(token,'[REDACTED_TEMPORARY_TEST_SESSION]')
p.write_text(s,encoding='utf-8')
print('Saved diagnostic sanitized.')
