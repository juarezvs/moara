from pathlib import Path
import tarfile
root=Path(__file__).resolve().parents[2]
with tarfile.open(root/'platform-source.tar','w') as archive:
 for folder in ('moara/gateway','moara/identity','moara/web','moara/tests'):
  for path in (root/folder).rglob('*'):
   if not path.is_file() or any(part in {'__pycache__','node_modules','dist','wheels','.angular'} for part in path.parts):continue
   archive.add(path,arcname=path.relative_to(root).as_posix())
 archive.add(root/'moara/__init__.py',arcname='moara/__init__.py')
print('Packaged source without dependencies, runtime data or credentials.')
