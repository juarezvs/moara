import json,subprocess,pathlib,tarfile,os,shutil
ROOT=pathlib.Path('/home/nutec/ai-server')
WORK=ROOT/'tmp/gpu-production';WORK.mkdir(parents=True,exist_ok=True)
os.umask(0o077)
def run(args):return subprocess.check_output(args,text=True).strip()
key=ROOT/'secrets/moara_gpu_tunnel_key'
if not key.exists():run(['ssh-keygen','-q','-t','ed25519','-N','','-C','moara-gpu-tunnel-20261029','-f',str(key)])
key.chmod(0o400)
print(json.dumps({'public_key':key.with_suffix('.pub').read_text().strip()}))
