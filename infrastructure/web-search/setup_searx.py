"""Pinned, private SearXNG. Settings secret stays in a mode-0600 host file."""
import pathlib,subprocess,json,secrets,time
root=pathlib.Path(__file__).resolve().parents[2]
image='searxng/searxng@sha256:9f59681775ba8d99744796e161d46dfecc771b972572edddb31d92dcfafc12b7'
folder=root/'data/searxng';folder.mkdir(parents=True,exist_ok=True);folder.chmod(0o700)
settings=folder/'settings.yml'
if not settings.exists():
 settings.write_text('''use_default_settings:
  engines:
    keep_only: [google, bing, duckduckgo, wikipedia, brave, qwant, startpage, yahoo]
general:
  instance_name: Moara Pesquisa Privada
search:
  safe_search: 1
  formats: [html, json]
server:
  secret_key: '''+secrets.token_hex(32)+'''
  limiter: false
  public_instance: false
  bind_address: 0.0.0.0
  port: 8080
outgoing:
  request_timeout: 6.0
  max_request_timeout: 10.0
engines:
  - name: google
    disabled: false
  - name: bing
    disabled: false
  - name: duckduckgo
    disabled: false
  - name: wikipedia
    disabled: false
  - name: brave
    disabled: false
  - name: qwant
    disabled: false
  - name: startpage
    disabled: false
  - name: yahoo
    disabled: false
''')
 settings.chmod(0o600)
for network,internal in [('moara-public-search',True),('moara-public-search-egress',False)]:
 if subprocess.run(['docker','network','inspect',network],capture_output=True).returncode:
  subprocess.run(['docker','network','create',*(['--internal'] if internal else []),network],check=True,capture_output=True)
name='moara-searxng'
if subprocess.run(['docker','inspect',name],capture_output=True).returncode:
 subprocess.run(['docker','create','--name',name,'--network','moara-public-search','--network-alias','moara-searxng',
  '--read-only','--tmpfs','/tmp:rw,size=64m','--tmpfs','/var/cache/searxng:rw,size=64m',
  '--cap-drop','ALL','--security-opt','no-new-privileges:true','--memory','512m','--cpus','1','--pids-limit','128',
  '-e','FORCE_OWNERSHIP=false','-e','GRANIAN_HOST=0.0.0.0','-e','GRANIAN_PORT=8080','-e','GRANIAN_WORKERS=1','-e','GRANIAN_RUNTIME_THREADS=2',
  '-v',str(settings)+':/etc/searxng/settings.yml:ro',image],capture_output=True,check=True)
 subprocess.run(['docker','network','connect','moara-public-search-egress',name],capture_output=True,check=True)
subprocess.run(['docker','start',name],capture_output=True,check=True)
subprocess.run(['docker','update','--restart','unless-stopped',name],capture_output=True,check=True)
for _ in range(45):
 r=subprocess.run(['docker','exec',name,'/usr/local/searxng/.venv/bin/python','-c',"import urllib.request;assert urllib.request.urlopen('http://localhost:8080/healthz',timeout=3).status==200"],capture_output=True)
 if r.returncode==0:break
 time.sleep(1)
else:raise RuntimeError('Private SearXNG did not become ready; inspect private logs')
report={'name':name,'image':image,'ready':True,'ports_published':False,'endpoint':'http://moara-searxng:8080'}
(root/'docs/runtime/searxng-service.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
