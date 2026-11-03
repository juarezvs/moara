import os,sys,subprocess,paramiko,shlex
from pathlib import Path

def source(script,timeout=180):
    p=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10','nutec@172.19.5.250','bash -s'],input=script.encode(),capture_output=True,timeout=timeout)
    if p.returncode: raise RuntimeError(p.stderr.decode(errors='replace')[-3000:])
    return p.stdout.decode(errors='replace')

def gpu():
    c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.RejectPolicy())
    key=paramiko.Ed25519Key(data=bytes.fromhex('00')) if False else None
    # Pin the key observed in the read-only inventory; no known_hosts mutation.
    class Pinned(paramiko.MissingHostKeyPolicy):
        def missing_host_key(self,client,hostname,key):
            if key.get_name()!='ssh-ed25519' or key.get_fingerprint().hex()!='e216e1966347690949065e60b57b1a14':
                raise paramiko.SSHException('GPU host key changed')
    c.set_missing_host_key_policy(Pinned())
    c.connect('172.19.5.246',username='nutec',password=os.environ['MOARA_GPU_SSH_PASSWORD'],timeout=15,allow_agent=False,look_for_keys=False)
    return c

def run(script,sudo=False):
    c=gpu()
    cmd=('sudo -S -p "" ' if sudo else '')+'bash -c '+shlex.quote(script)
    i,o,e=c.exec_command(cmd,timeout=1800)
    if sudo: i.write(os.environ['MOARA_GPU_SSH_PASSWORD']+'\n');i.flush()
    for line in o: print(line,end='',flush=True)
    err=e.read().decode(errors='replace'); rc=o.channel.recv_exit_status();c.close()
    if err: print(err,flush=True)
    if rc: raise SystemExit(rc)

if __name__=='__main__':
    run(Path(sys.argv[1]).read_text(encoding='utf8'),sudo='--sudo' in sys.argv)
