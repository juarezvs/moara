set -eu
docker stop moara-gpu-validation
iptables -D DOCKER-USER -p tcp -m conntrack --ctdir ORIGINAL --ctorigdst 172.19.5.246 --ctorigdstport 11435 ! -s 172.19.5.250 -j DROP
python3 - <<'PY'
import pathlib,os,signal
p=pathlib.Path('/proc/125069/cmdline')
if p.exists() and b'nvidia-smi' in p.read_bytes() and p.read_bytes().startswith(b'timeout\0'):
 os.kill(125069,signal.SIGTERM)
PY
docker inspect moara-gpu-validation --format 'validation_container={{.State.Status}} restart_policy={{.HostConfig.RestartPolicy.Name}}'
ss -lnt | grep 11435 || true
free -h
nvidia-smi --query-gpu=memory.used,temperature.gpu --format=csv
