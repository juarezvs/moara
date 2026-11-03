from pathlib import Path
import subprocess,json
root=Path('/home/nutec/ai-server')
for name in ['ai-server-webui-1','ai-server-caddy-1']:
 item=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
 print(json.dumps({'container':name,'running':item['State']['Running'],'health':item['State'].get('Health',{}).get('Status'),'image':item['Image']}))
 assert item['State']['Running']
print(json.dumps({'backup_verified':json.loads((root/'docs/runtime/moara-preservation-latest.json').read_text())['verified']}))
source=(root/'infrastructure/caddy/Caddyfile').read_text()
assert 'max_size 32MB' in source and 'max_size 2MB' in source
print('Upload-specific limit and existing fallback confirmed.')
