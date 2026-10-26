"""Resolve public pinned requirements into an offline, SHA-256 locked wheelhouse."""
import hashlib
import json
import subprocess
import zipfile
from email.parser import BytesParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
folder=ROOT/'moara/gateway';destination=folder/'wheels-next'
destination.mkdir(exist_ok=True)
args=['docker','run','--rm','--user','0:0','--network','ai-server_download','--cap-drop','ALL','--security-opt','no-new-privileges:true',
    '--memory','768m','--cpus','1','--mount',f'type=bind,source={destination},target=/wheels',
    '--mount',f'type=bind,source={folder}/requirements.txt,target=/requirements.txt,readonly',
    'ai-gateway:runtime-20261020','python','-m','pip','download','--only-binary=:all:','--no-cache-dir','--dest','/wheels','-r','/requirements.txt']
result=subprocess.run(args,capture_output=True,text=True,timeout=300)
(ROOT/'docs/runtime/moara-python-download.log').write_text(result.stdout+result.stderr)
if result.returncode:raise RuntimeError('Public Python wheel resolution failed; see sanitized download log')
packages={};lines=[]
for path in sorted(destination.glob('*.whl')):
    with zipfile.ZipFile(path) as archive:
        metadata=BytesParser().parsebytes(archive.read(next(p for p in archive.namelist() if p.endswith('.dist-info/METADATA'))))
    name,version=metadata['Name'],metadata['Version'];normalized=name.lower().replace('_','-')
    if normalized in packages and packages[normalized]['version']!=version:raise RuntimeError('Ambiguous wheel versions')
    packages[normalized]={'name':name,'version':version,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
for name,row in sorted(packages.items()):lines.append(f"{row['name']}=={row['version']} --hash=sha256:{row['sha256']}")
old=folder/'wheels';backup=folder/'wheels-before-otel'
if old.exists():
    if backup.exists():raise RuntimeError('Previous wheelhouse preservation already exists; inspect before replacing')
    old.rename(backup)
destination.rename(old)
(folder/'requirements.lock').write_text('\n'.join(lines)+'\n')
(ROOT/'docs/runtime/moara-python-lock.json').write_text(json.dumps({'packages':packages,'offline_hashes_required':True},indent=2))
print('MOARA_HASH_LOCK_READY',len(packages))
