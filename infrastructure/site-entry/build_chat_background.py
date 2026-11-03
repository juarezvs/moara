"""Build and privately stage the frontend over the exact running application."""
import pathlib,subprocess,json,shutil,time
root=pathlib.Path(__file__).resolve().parents[2];tag='moara-core:chat-background-20261102';base='moara-core:pre-chat-background-app-20261102'
original=json.loads(subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1']))[0]
if subprocess.run(['docker','image','inspect',base],capture_output=True).returncode:subprocess.run(['docker','tag',original['Image'],base],check=True)
folder=root/'tmp/chat-background-build';folder.mkdir(exist_ok=True);shutil.copytree(root/'moara/web/dist/moara-web/browser',folder/'web',dirs_exist_ok=True)
(folder/'Dockerfile').write_text('FROM '+base+'\nCOPY web /app/web\n')
subprocess.run(['docker','build','--network','none','-t',tag,str(folder)],check=True)
image=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip();name='moara-chat-background-stage-'+image.split(':')[1][:10]
if subprocess.run(['docker','inspect',name],capture_output=True).returncode:
 networks=list(original['NetworkSettings']['Networks']);args=['docker','create','--name',name,'--network',networks[0],'--read-only','--tmpfs','/tmp:size=128m','--memory','1g','--cpus','2','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges:true']
 env=dict(v.split('=',1) for v in original['Config']['Env']);env['MOARA_BACKGROUND_JOBS']='false'
 for k,v in env.items():args+=['-e',k+'='+v]
 for m in original['Mounts']:
  if m['Destination'].startswith(('/run/secrets/','/app/legal_catalog/')):args+=['--mount',f"type=bind,src={m['Source']},dst={m['Destination']},readonly"]
 args+=[image]+original['Config']['Cmd'];subprocess.run(args,check=True,stdout=subprocess.DEVNULL)
 for network in networks[1:]:subprocess.run(['docker','network','connect',network,name],check=True)
subprocess.run(['docker','start',name],check=True,stdout=subprocess.DEVNULL)
for _ in range(40):
 r=subprocess.run(['docker','exec',name,'python','-c',"import urllib.request;assert urllib.request.urlopen('http://localhost:8075/api/v1/ready',timeout=3).status==200"],capture_output=True)
 if not r.returncode:break
 time.sleep(1)
else:raise RuntimeError('Private UI candidate not ready')
(root/'tmp/chat-background-stage.json').write_text(json.dumps({'core':name,'image':image,'base_image':original['Image'],'frontend_only':True}))
print(json.dumps({'private_candidate':name,'image':image,'frontend_only':True,'ports_published':False}))
