import json,os,shlex,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from gpu_remote import gpu
script=r'''
set -eu
hostname
cat /etc/os-release | head -5
free -b
lscpu | head -18
df -B1 /
nvidia-smi --query-gpu=name,uuid,driver_version,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu --format=csv
systemctl is-active moara-gpu.service moara-gpu-warm.timer
systemctl is-enabled moara-gpu.service moara-gpu-warm.timer
docker ps --format '{{.Names}} {{.Image}} {{.Status}}'
docker exec moara-gpu-ollama ollama ps
docker exec moara-gpu-embeddings ollama ps
curl --fail --silent http://127.0.0.1:11434/api/ps
curl --fail --silent http://127.0.0.1:11435/api/ps
ss -lnt | grep -E '11434|11435'
'''
client=gpu()
stdin,stdout,stderr=client.exec_command('sudo -S -p "" bash -c '+shlex.quote(script),timeout=90)
stdin.write(os.environ['MOARA_GPU_SSH_PASSWORD']+'\n');stdin.flush()
output=stdout.read().decode(errors='replace');errors=stderr.read().decode(errors='replace');status=stdout.channel.recv_exit_status();client.close()
result={'host':'172.19.5.246','exit_code':status,'inventory':output,'diagnostic_errors':errors}
target=Path('output/moara2');target.mkdir(parents=True,exist_ok=True)
(target/'gpu-inventory-20261030.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
raise SystemExit(status)
