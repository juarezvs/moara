"""Activate only validated gateway images; retain data and rollback images."""
import pathlib,subprocess,time,json
root=pathlib.Path(__file__).resolve().parents[2];wrapper=root/'moara/infrastructure/scripts/compose.sh'
backup=root/'backups/moara2-20261030/compose-before';backup.parent.mkdir(exist_ok=True)
if not backup.exists():backup.write_bytes(wrapper.read_bytes())
s=wrapper.read_text()
for overlay in ['gpu-tls-compose.yml','moara2-compose.yml']:
    if overlay not in s:s=s.replace(' "$@"',' \\\n -f moara/infrastructure/'+overlay+' "$@"')
wrapper.write_text(s);wrapper.chmod(0o755)
command=['sh',str(wrapper)]
# Migrations 8 and 9 are additive, already applied, and used by the private candidate.
subprocess.run(command+['config','--quiet'],cwd=root,check=True)
subprocess.run(command+['up','-d','--no-deps','gateway','moara-gateway'],cwd=root,check=True)
for _ in range(45):
    output=subprocess.run(['docker','exec','ai-server-moara-gateway-1','python','-c',
        'import urllib.request;print(urllib.request.urlopen("http://localhost:8075/api/v1/ready",timeout=3).status)'],capture_output=True)
    if output.returncode==0:break
    time.sleep(1)
else:raise RuntimeError('New core gateway did not become ready; inspect before continuing')
print(json.dumps({'core':'moara-core:2.0-foundation-20261030','inference_gateway':'ai-gateway:mtls-20261030','ready':True}))
