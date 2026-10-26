import http.client,json,socket,ssl,subprocess,sys
from pathlib import Path
base=Path(sys.argv[1]);host='moara.am.trf1.gov.br'
addresses=sorted({row[4][0] for row in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)})
assert '172.19.5.250' in addresses,'Unexpected institutional DNS destination'
ca=base/'moara-public-ca.crt'
subprocess.run(['docker','cp','ai-server-caddy-1:/data/caddy/pki/authorities/moara/root.crt',str(ca)],check=True,capture_output=True)
context=ssl.create_default_context(cafile=str(ca))
result={'hostname':host,'addresses':addresses,'certificate_verification':True,'routes':{}}
for path in ['/','/moara/','/studio/','/health','/moara/api/v1/auth/me','/moara/api/v1/admin/accounts']:
 connection=http.client.HTTPSConnection(host,443,context=context,timeout=15)
 connection.request('GET',path)
 response=connection.getresponse()
 result['routes'][path]=response.status
 connection.close()
 expected=[401,403] if '/api/v1/' in path else [200]
 assert response.status in expected,(path,response.status)
(base/'tls-smoke.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
