import io,json,os,subprocess,tarfile,time
from pathlib import Path
ROOT=Path('/home/nutec/ai-server');STAGE=Path('/home/nutec/moara-platform-20261026-r2')
def run(args,**kwargs):
 p=subprocess.run(args,capture_output=True,timeout=180,**kwargs)
 if p.returncode:raise RuntimeError(p.stderr.decode()[-1000:])
 return p.stdout
names=['moara-platform-browser','moara-platform-proxy']
for name in names:
 p=subprocess.run(['docker','inspect',name],capture_output=True)
 if p.returncode==0:
  if json.loads(p.stdout)[0]['Config'].get('Labels',{}).get('moara.test')!='platform-ui':raise RuntimeError('unowned fixture')
  run(['docker','rm','-f',name])
config=STAGE/'Caddyfile.qa';config.write_text('https://localhost:8443 {\n tls internal\n reverse_proxy moara-platform-qa-api:8075\n}\n')
run(['docker','run','-d','--name',names[1],'--label','moara.test=platform-ui','--network','moara-platform-qa-isolated','--memory','128m','--cpus','1',
 '--mount',f'type=bind,source={config},target=/etc/caddy/Caddyfile,readonly','--tmpfs','/data:size=16m','--tmpfs','/config:size=16m','ai-caddy:2.11.7'])
run(['docker','run','-d','--name',names[0],'--label','moara.test=platform-ui','--network','container:'+names[1],'--memory','1g','--cpus','2','--pids-limit','256',
 '--entrypoint','sleep','ia-studio-renderer:1.0.0','infinity'])
run(['docker','cp',str(STAGE/'moara/tests/platform_browser.py'),names[0]+':/tmp/test.py'])
fixture={'password':(ROOT/'secrets/moara-platform-qa/admin_password').read_text()}
p=subprocess.run(['docker','exec','-i',names[0],'python','/tmp/test.py'],input=json.dumps(fixture).encode(),capture_output=True,timeout=180)
print(p.stdout.decode());print(p.stderr.decode().replace(fixture['password'],'[REDACTED]')[-4000:])
if p.returncode:raise SystemExit(p.returncode)
destination=STAGE/'browser-evidence';destination.mkdir(exist_ok=True)
data=run(['docker','exec',names[0],'tar','-C','/tmp/platform-browser','-cf','-','.'])
with tarfile.open(fileobj=io.BytesIO(data)) as tar:tar.extractall(destination,filter='data')
