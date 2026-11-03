"""Operator helper: secrets are generated and kept on their owning servers."""
import sys,pathlib,json,base64,shlex
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'tmp'))
from gpu_remote import gpu,source
ROOT=pathlib.Path(__file__).resolve().parents[2]

def remote(command):
    import os
    client=gpu()
    try:
        stdin,stdout,stderr=client.exec_command('sudo -S -p "" bash -c '+shlex.quote(command),timeout=60)
        stdin.write(os.environ['MOARA_GPU_SSH_PASSWORD']+'\n');stdin.flush()
        output=stdout.read().decode();error=stderr.read().decode();status=stdout.channel.recv_exit_status()
        if status:raise RuntimeError(error[-1800:])
        return output
    finally:client.close()

source('''set -eu
cd /home/nutec/ai-server
umask 077
mkdir -p secrets/gpu-pki
if [ ! -f secrets/gpu-pki/ca.key ]; then
 openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out secrets/gpu-pki/ca.key
 openssl req -new -x509 -key secrets/gpu-pki/ca.key -sha256 -days 1825 -subj '/CN=Moara GPU Private Transport CA' -addext 'basicConstraints=critical,CA:TRUE,pathlen:0' -addext 'keyUsage=critical,keyCertSign,cRLSign' -out secrets/moara_gpu_ca.crt
fi
if [ ! -f secrets/moara_gpu_client.key ]; then
 openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out secrets/moara_gpu_client.key
 openssl req -new -key secrets/moara_gpu_client.key -subj '/CN=moara-inference-gateway' -out secrets/gpu-pki/client.csr
 printf 'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=clientAuth\n' > secrets/gpu-pki/client.ext
 openssl x509 -req -in secrets/gpu-pki/client.csr -CA secrets/moara_gpu_ca.crt -CAkey secrets/gpu-pki/ca.key -CAcreateserial -days 365 -sha256 -extfile secrets/gpu-pki/client.ext -out secrets/moara_gpu_client.crt
fi
chmod 700 secrets/gpu-pki
chmod 600 secrets/gpu-pki/*
chmod 644 secrets/moara_gpu_ca.crt secrets/moara_gpu_client.crt secrets/moara_gpu_client.key
''')
csr=remote('''set -eu
umask 077
install -d -m 700 /etc/moara-gpu-tls
if [ ! -f /etc/moara-gpu-tls/server.key ]; then
 openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out /etc/moara-gpu-tls/server.key
 openssl req -new -key /etc/moara-gpu-tls/server.key -subj '/CN=moara-gpu-tunnel-tls' -out /etc/moara-gpu-tls/server.csr
fi
cat /etc/moara-gpu-tls/server.csr
''')
assert csr.startswith('-----BEGIN CERTIFICATE REQUEST-----')
encoded=base64.b64encode(csr.encode()).decode()
source('''set -eu
cd /home/nutec/ai-server
umask 077
printf %s '''+shlex.quote(encoded)+''' | base64 -d > secrets/gpu-pki/server.csr
printf 'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:moara-gpu-tunnel-tls\n' > secrets/gpu-pki/server.ext
openssl x509 -req -in secrets/gpu-pki/server.csr -CA secrets/moara_gpu_ca.crt -CAkey secrets/gpu-pki/ca.key -CAcreateserial -days 365 -sha256 -extfile secrets/gpu-pki/server.ext -out secrets/gpu-pki/server.crt
openssl verify -CAfile secrets/moara_gpu_ca.crt -purpose sslserver secrets/gpu-pki/server.crt
''')
public=json.loads(source('''python3 - <<'PY'
import pathlib,json
p=pathlib.Path('/home/nutec/ai-server/secrets')
print(json.dumps({name:(p/filename).read_text() for name,filename in [('ca.crt','moara_gpu_ca.crt'),('server.crt','gpu-pki/server.crt')]}))
PY
'''))
files={'/etc/moara-gpu-tls/'+name:content.encode() for name,content in public.items()}
files['/opt/moara-gpu/tls_proxy.py']=(ROOT/'infrastructure/gpu/tls_proxy.py').read_bytes()
files['/etc/systemd/system/moara-gpu-tls.service']=(ROOT/'infrastructure/gpu/moara-gpu-tls.service').read_bytes()
payload={name:base64.b64encode(content).decode() for name,content in files.items()}
remote("python3 - <<'PY'\nimport json,pathlib,base64\nfor name,value in json.loads("+repr(json.dumps(payload))+").items():\n p=pathlib.Path(name);p.write_bytes(base64.b64decode(value));p.chmod(0o600 if name.startswith('/etc/moara-gpu-tls/') else 0o644)\nPY\nsystemctl daemon-reload\nsystemctl enable --now moara-gpu-tls.service\nsystemctl is-active moara-gpu-tls.service")
# Restrict the existing inference SSH key to exactly these loopback targets.
remote(r'''python3 - <<'PY'
from pathlib import Path
p=Path('/home/nutec/.ssh/authorized_keys');original=p.read_text();lines=original.splitlines();changed=[]
for line in lines:
 if 'permitopen="127.0.0.1:11434"' in line and 'permitopen="127.0.0.1:11435"' in line and 'command="/bin/false"' in line:
  for port in [11443,11444,11445]:
   option='permitopen="127.0.0.1:'+str(port)+'"'
   if option not in line:line=line.replace(' ssh-ed25519',','+option+' ssh-ed25519',1)
  changed.append(line)
 else:changed.append(line)
result='\n'.join(changed)+'\n'
assert result!=original or all('permitopen="127.0.0.1:'+str(port)+'"' in original for port in [11443,11444,11445])
backup=p.with_name('authorized_keys.before-mtls-20261030')
if not backup.exists():backup.write_text(original);backup.chmod(0o600)
p.write_text(result);p.chmod(0o600)
PY''')
print('GPU_MTLS_SERVICE_PROVISIONED_NO_MODEL_RESTART')
