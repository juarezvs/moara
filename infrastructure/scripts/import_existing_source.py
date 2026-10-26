"""Import an explicit selection of source files; never import runtime data."""
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REMOTE = r'''
import base64,hashlib,json
from pathlib import Path
root=Path('/home/nutec/ai-server')
trees=['moara/web/src','moara/gateway','moara/identity']
exact=['moara/__init__.py','moara/web/package.json','moara/web/package-lock.json',
 'moara/web/angular.json','moara/web/tsconfig.json','moara/web/tsconfig.app.json',
 'moara/web/.postcssrc.json','backups/backup.py','infrastructure/scripts/backup.sh',
 'moara/infrastructure/scripts/preservation.py','moara/infrastructure/scripts/compose.sh']
files=[root/p for p in exact]
for tree in trees:
 for p in (root/tree).rglob('*'):
  if any(x in p.relative_to(root/tree).parts for x in ['wheels','wheels-before-otel','__pycache__','node_modules','dist','.angular']):continue
  if p.suffix in ['.py','.ts','.html','.css','.json','.txt','.lock','.ini','.sql','.md'] or p.name=='Dockerfile':files.append(p)
files.extend((root/'moara/tests').glob('test_*.py'))
result={}
for p in sorted(set(files)):
 if p.is_symlink() or not p.is_file():continue
 relative=p.relative_to(root).as_posix()
 if p.stat().st_size>2*1024**2:raise RuntimeError('Source file too large: '+relative)
 content=p.read_bytes()
 result[relative]={'sha256':hashlib.sha256(content).hexdigest(),'base64':base64.b64encode(content).decode()}
print(json.dumps(result))
'''


def main():
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o',
        'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
        'nutec@172.19.5.250', 'python3 -'], input=REMOTE.encode(),
        capture_output=True, timeout=120, check=True)
    records = json.loads(result.stdout)
    staged = []
    for name, record in records.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or ':' in name:
            raise ValueError('Unsafe source path')
        path = ROOT.joinpath(*relative.parts)
        content = base64.b64decode(record['base64'], validate=True)
        if hashlib.sha256(content).hexdigest() != record['sha256']:
            raise ValueError('Source checksum mismatch')
        if path.exists() and path.read_bytes() != content:
            raise FileExistsError(f'Refusing to replace local work: {name}')
        staged.append((path, content))
    for path, content in staged:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    manifest = {'host': '172.19.5.250', 'root': '/home/nutec/ai-server',
                'files': {name: record['sha256'] for name, record in records.items()}}
    target = ROOT / 'docs' / 'SOURCE_ORIGIN.json'
    target.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(f'Imported {len(records)} source files; SHA256 manifest: {target}')


if __name__ == '__main__':
    main()
