set -eu
umask 077
install -d -m 755 /opt/moara-gpu
if [ ! -d /srv/moara-inference ]; then
  test -d /home/nutec/moara-gpu-validation/models
  test "$(docker inspect moara-gpu-validation --format '{{.State.Running}}')" = false
  mv /home/nutec/moara-gpu-validation /srv/moara-inference
fi
if docker container inspect moara-gpu-validation >/dev/null 2>&1; then docker rm moara-gpu-validation; fi
install -m 644 /home/nutec/moara-gpu-install/compose.yml /opt/moara-gpu/compose.yml
install -m 644 /home/nutec/moara-gpu-install/keep_warm.py /opt/moara-gpu/keep_warm.py
for unit in moara-gpu.service moara-gpu-warm.service moara-gpu-warm.timer; do
  install -m 644 "/home/nutec/moara-gpu-install/$unit" "/etc/systemd/system/$unit"
done
python3 - <<'PY'
from pathlib import Path
import pwd,os
pub=Path('/home/nutec/moara-gpu-install/tunnel.pub').read_text().strip()
assert pub.startswith('ssh-ed25519 ') and 'moara-gpu-tunnel-20261029' in pub
directory=Path('/home/nutec/.ssh');directory.mkdir(mode=0o700,exist_ok=True)
p=directory/'authorized_keys'
old=p.read_text() if p.exists() else ''
lines=[line for line in old.splitlines() if 'moara-gpu-tunnel-20261029' not in line]
lines.append('from="172.19.5.250",restrict,port-forwarding,permitopen="127.0.0.1:11434",command="/bin/false" '+pub)
p.write_text('\n'.join(lines)+'\n');p.chmod(0o600);directory.chmod(0o700)
uid=pwd.getpwnam('nutec').pw_uid;gid=pwd.getpwnam('nutec').pw_gid
os.chown(directory,uid,gid);os.chown(p,uid,gid)
PY
systemctl daemon-reload
systemctl enable --now moara-gpu.service moara-gpu-warm.timer
systemctl is-active moara-gpu.service moara-gpu-warm.timer
docker exec moara-gpu-ollama ollama ps
ss -lnt | grep 11434
