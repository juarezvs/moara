"""Stop private acceptance candidates; preserve containers, images and data."""
import subprocess,json
rows=[json.loads(line) for line in subprocess.check_output(['docker','ps','--format','json'],text=True).splitlines()]
names=[row['Names'] for row in rows if row['Names'].startswith('moara2-stage-') or row['Names']=='moara-gateway-mtls-stage-20261030']
if names:subprocess.run(['docker','stop',*names],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['docker','stop','ai-server-moara-gpu-tunnel-1'],check=True,stdout=subprocess.DEVNULL)
print(json.dumps({'private_candidates_stopped':names,'legacy_plaintext_relay_stopped':True,'containers_and_images_preserved':True}))
