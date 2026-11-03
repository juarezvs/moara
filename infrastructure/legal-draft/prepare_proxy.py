"""TLS private candidate: real streaming passes through without browser interception."""
import pathlib,subprocess,json,hashlib,time
root=pathlib.Path(__file__).resolve().parents[2]
stage=json.loads((root/'tmp/legal-draft-stage.json').read_text());core=stage['core']
folder=root/'tmp/legal-draft-tls';folder.mkdir(exist_ok=True);folder.chmod(0o700)
certs=folder/'certs';certs.mkdir(exist_ok=True);certs.chmod(0o700)
for suffix in ['crt','key']:
 target=certs/('moara.'+suffix)
 subprocess.run(['docker','cp','ai-server-caddy-1:/data/caddy/certificates/moara/moara.am.trf1.gov.br/moara.am.trf1.gov.br.'+suffix,str(target)],capture_output=True,check=True)
 target.chmod(0o600)
source=(root/'infrastructure/caddy/Caddyfile').read_text()
routes=source[source.index('(moara_routes) {'):source.index('https://localhost:8443')]
routes=routes.replace('moara-gateway:8075',core+':8075')
config='{\n admin off\n auto_https off\n}\n'+routes+'\nhttps://moara.am.trf1.gov.br:443 {\n tls /certs/moara.crt /certs/moara.key\n import moara_routes\n}\n'
(folder/'Caddyfile').write_text(config)
original=json.loads(subprocess.check_output(['docker','inspect','ai-server-caddy-1']))[0]
name='moara-legal-draft-tls-'+hashlib.sha256(config.encode()).hexdigest()[:10]
if subprocess.run(['docker','inspect',name],capture_output=True).returncode:
 args=['docker','create','--name',name,'--network','ai-server_frontend','--read-only','--tmpfs','/tmp:size=32m','--tmpfs','/data:size=32m','--tmpfs','/config:size=16m','--cap-drop','ALL','--security-opt','no-new-privileges:true','--memory','128m','--cpus','1','--pids-limit','64',
       '-v',str(folder/'Caddyfile')+':/etc/caddy/Caddyfile:ro','-v',str(certs)+':/certs:ro',original['Image'],'caddy','run','--config','/etc/caddy/Caddyfile','--adapter','caddyfile']
 subprocess.run(args,check=True,capture_output=True)
 for network in original['NetworkSettings']['Networks']:
  if network!='ai-server_frontend':subprocess.run(['docker','network','connect',network,name],check=True,capture_output=True)
subprocess.run(['docker','start',name],check=True,capture_output=True)
ip=json.loads(subprocess.check_output(['docker','inspect',name]))[0]['NetworkSettings']['Networks']['ai-server_frontend']['IPAddress']
(root/'tmp/legal-draft-proxy.json').write_text(json.dumps({'name':name,'ip':ip,'ports_published':False,'streaming_unbuffered':True}))
print(json.dumps({'private_tls_proxy':name,'ports_published':False,'streaming_unbuffered':True}))
