set -eu
python3 - <<'PY'
from pathlib import Path
p=Path('/home/nutec/.ssh/authorized_keys');original=p.read_text();changed=[];found=False
for line in original.splitlines():
 if 'command="/bin/false"' in line and 'permitopen="127.0.0.1:11443"' in line:
  found=True
  for port in [11434,11435]:
   line=line.replace('permitopen="127.0.0.1:'+str(port)+'",','')
  assert all('permitopen="127.0.0.1:'+str(port)+'"' in line for port in [11443,11444,11445])
  assert all('permitopen="127.0.0.1:'+str(port)+'"' not in line for port in [11434,11435])
 changed.append(line)
assert found
p.write_text('\n'.join(changed)+'\n');p.chmod(0o600)
print('INFERENCE_SSH_KEY_RESTRICTED_TO_TLS_PORTS')
PY
systemctl is-active moara-gpu-tls.service
