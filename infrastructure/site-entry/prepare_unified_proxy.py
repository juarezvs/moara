"""Validate the unified public entry without altering live routing."""
import pathlib,subprocess,json,re,hashlib
root=pathlib.Path(__file__).resolve().parents[2];folder=root/'tmp/unified-proxy';folder.mkdir(exist_ok=True)
live=root/'infrastructure/caddy/Caddyfile';original=live.read_text();backup=root/'backups/unified-20261031';backup.mkdir(exist_ok=True)
if not (backup/'Caddyfile-before').exists():(backup/'Caddyfile-before').write_text(original)
block='''  # MOARA_PRIMARY_ENTRY_BEGIN
  @moara_primary_entry {
    path /
    method GET HEAD
  }
  header @moara_primary_entry Cache-Control "no-store"
  redir @moara_primary_entry /moara/chat 302
  redir /chat-anterior /moara/chat?area=historico 302
  redir /chat-anterior/ /moara/chat?area=historico 302
  # MOARA_PRIMARY_ENTRY_END
'''
candidate=re.sub(r'  # MOARA_PRIMARY_ENTRY_BEGIN.*?  # MOARA_PRIMARY_ENTRY_END\n',lambda _:block,original,flags=re.S)
old='''  handle {
    request_body {
      max_size 2MB
    }
    reverse_proxy webui:8080
  }
'''
new='''  # Institutional services stay private behind their existing authentication.
  handle /static/moara/* {
    reverse_proxy webui:8080
  }
  @institutional_services path /api/* /socket.io/* /ws/* /oauth/*
  handle @institutional_services {
    request_body {
      max_size 2MB
    }
    reverse_proxy webui:8080 {
      @previous_ui header Content-Type text/html*
      handle_response @previous_ui {
        redir * /moara/chat 302
      }
    }
  }
  handle {
    @previous_conversation path_regexp prior ^/c/([0-9a-fA-F-]{36})/?$
    redir @previous_conversation /moara/chat?previous={re.prior.1} 302
    redir * /moara/chat 302
  }
'''
assert candidate.count(old)==1;candidate=candidate.replace(old,new,1)
(folder/'Caddyfile-candidate').write_text(candidate)
subprocess.run(['docker','exec','-i','ai-server-caddy-1','sh','-c','cat > /tmp/moara-unified.Caddyfile && caddy validate --config /tmp/moara-unified.Caddyfile --adapter caddyfile'],input=candidate,text=True,check=True,capture_output=True)
native=(root/'tmp/unified-core-name.txt').read_text().strip()
start=candidate.index('(moara_routes) {');end=candidate.index('https://localhost:8443',start)
stage='{\n admin off\n auto_https off\n}\n'+candidate[start:end]+ '\nhttp://:8080 {\n import moara_routes\n}\n'
stage=stage.replace('moara-gateway:8075',native+':8075')
(folder/'Caddyfile-stage').write_text(stage)
original_container=json.loads(subprocess.check_output(['docker','inspect','ai-server-caddy-1']))[0]
name='moara-unified-proxy-stage-'+native.split('-')[-1]+'-'+hashlib.sha256(stage.encode()).hexdigest()[:8]
if subprocess.run(['docker','inspect',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
 networks=list(original_container['NetworkSettings']['Networks'])
 args=['docker','create','--name',name,'--network',networks[0],'--read-only','--tmpfs','/tmp:size=32m','--tmpfs','/data:size=32m','--tmpfs','/config:size=16m','--cap-drop','ALL','--security-opt','no-new-privileges:true','--memory','128m','--cpus','1','--pids-limit','64','-v',str(folder/'Caddyfile-stage')+':/etc/caddy/Caddyfile:ro',original_container['Image'],'caddy','run','--config','/etc/caddy/Caddyfile','--adapter','caddyfile']
 subprocess.run(args,check=True,capture_output=True)
 for network in networks[1:]:subprocess.run(['docker','network','connect',network,name],check=True,capture_output=True)
subprocess.run(['docker','start',name],check=True,capture_output=True)
(root/'tmp/unified-proxy-name.txt').write_text(name)
print(json.dumps({'proxy':name,'production_changed':False,'ports_published':False,'candidate_validated':True}))
