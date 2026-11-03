set -eu
systemctl stop moara-gpu-warm.timer
python3 - <<'PY'
from pathlib import Path
p=Path('/home/nutec/.ssh/authorized_keys')
lines=p.read_text().splitlines()
lines=[line.replace('permitopen="127.0.0.1:11434",','permitopen="127.0.0.1:11434",permitopen="127.0.0.1:11435",') if 'moara-gpu-tunnel-20261029' in line and 'permitopen="127.0.0.1:11435"' not in line else line for line in lines]
p.write_text('\n'.join(lines)+'\n');p.chmod(0o600)
PY
install -m 644 /home/nutec/moara-gpu-install/compose.yml /opt/moara-gpu/compose.yml
install -m 644 /home/nutec/moara-gpu-install/keep_warm.py /opt/moara-gpu/keep_warm.py
