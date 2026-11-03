"""Prepare and validate Caddy routing; leave production configuration untouched."""
import pathlib,subprocess,json,re
root=pathlib.Path(__file__).resolve().parents[2]
folder=root/'tmp/primary-entry';folder.mkdir(exist_ok=True)
live=root/'infrastructure/caddy/Caddyfile';original=live.read_text()
backup=root/'backups/primary-entry-20261030/Caddyfile-before';backup.parent.mkdir(exist_ok=True)
if not backup.exists():backup.write_text(original)
block=(root/'infrastructure/site-entry/root-routes.caddy').read_text()
assert original.count('(moara_routes) {')==1
if 'MOARA_PRIMARY_ENTRY_BEGIN' in original:
 candidate=re.sub(r'  # MOARA_PRIMARY_ENTRY_BEGIN.*?  # MOARA_PRIMARY_ENTRY_END\n',lambda _:block,original,flags=re.S)
else:candidate=original.replace('(moara_routes) {','(moara_routes) {\n'+block,1)
(folder/'Caddyfile-candidate').write_text(candidate)
# Validate with the exact running binary and its existing protected CA storage.
command=['docker','exec','-i','ai-server-caddy-1','sh','-c','cat > /tmp/moara-primary-entry.Caddyfile && caddy validate --config /tmp/moara-primary-entry.Caddyfile --adapter caddyfile']
subprocess.run(command,input=candidate,text=True,check=True)
start=candidate.index('(moara_routes) {');end=candidate.index('https://localhost:8443',start)
stage='{\n admin off\n auto_https off\n}\n'+candidate[start:end]+'\nhttp://:8080 {\n import moara_routes\n}\n'
(folder/'Caddyfile-stage').write_text(stage)
original_container=json.loads(subprocess.check_output(['docker','inspect','ai-server-caddy-1']))[0]
name='moara-primary-entry-proxy-stage-20261030'
if subprocess.run(['docker','inspect',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
 networks=list(original_container['NetworkSettings']['Networks'])
 args=['docker','create','--name',name,'--network',networks[0],'--read-only','--tmpfs','/tmp:size=32m',
  '--tmpfs','/data:size=32m','--tmpfs','/config:size=16m','--cap-drop','ALL','--security-opt','no-new-privileges:true',
  '--memory','128m','--cpus','1','--pids-limit','64','-v',str(folder/'Caddyfile-stage')+':/etc/caddy/Caddyfile:ro',original_container['Image'],
  'caddy','run','--config','/etc/caddy/Caddyfile','--adapter','caddyfile']
 subprocess.run(args,check=True,stdout=subprocess.DEVNULL)
 for network in networks[1:]:subprocess.run(['docker','network','connect',network,name],check=True)
subprocess.run(['docker','start',name],check=True,stdout=subprocess.DEVNULL)
print(json.dumps({'proxy_candidate':name,'public_ports':False,'production_config_changed':False}))
