"""Run in the isolated backup helper; stdout contains hashes/metadata only.

Source is mounted read-only. Files created in the private snapshot belong to the
rootless Docker owner; the original owners and permissions are never changed.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat

SOURCES = ('infrastructure', 'gateway', 'inference', 'agents', 'integrations',
           'ia-studio', 'connectors', 'moara', 'docs', 'tests', 'secrets',
           'backups/backup.py', 'README.md', '.gitignore')
EXCLUDED_DIRS = {'node_modules', '__pycache__', '.venv', '.angular', '.git',
                 'wheels', 'wheels-before-otel'}


def collect(source, destination):
    source, destination = Path(source), Path(destination)
    report = {'files': {}, 'excluded': {}}

    def walk(path):
        relative = path.relative_to(source).as_posix()
        parts = Path(relative).parts
        reason = None
        if any(part in EXCLUDED_DIRS for part in parts):
            reason = 'reproducible_dependency_or_cache'
        elif relative == 'docs/runtime':
            reason = 'runtime_evidence'
        elif relative == 'secrets/backup_key':
            reason = 'key_stored_separately'
        elif 'dist' in parts and not relative.startswith('moara/web/dist'):
            reason = 'generated_build'
        if reason:
            report['excluded'][relative] = reason
            return
        if path.is_symlink():
            raise RuntimeError('Configuration symlink requires explicit review: '+relative)
        before = path.stat()
        if stat.S_ISDIR(before.st_mode):
            entries = sorted(path.iterdir())
            for child in entries:
                walk(child)
            if [p.name for p in entries] != sorted(p.name for p in path.iterdir()):
                raise RuntimeError('Configuration file set changed: '+relative)
            return
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeError('Unsupported configuration file: '+relative)
        if before.st_size > 32*1024**2 and parts[0] != 'secrets':
            report['excluded'][relative] = 'large_non_secret_artifact'
            return
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # O_NOFOLLOW closes the symlink race between inspection and open.
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(descriptor, 'rb') as original, target.open('xb') as copied:
            opened = os.fstat(original.fileno())
            if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                raise RuntimeError('Configuration replaced during preservation: '+relative)
            shutil.copyfileobj(original, copied, 1024**2)
            after = os.fstat(original.fileno())
        current = path.stat(follow_symlinks=False)
        fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if fields(before) != fields(after) or fields(after) != fields(current):
            raise RuntimeError('Configuration changed during preservation: '+relative)
        target.chmod(0o600)
        digest = hashlib.sha256()
        with target.open('rb') as content:
            for block in iter(lambda: content.read(1024**2), b''):
                digest.update(block)
        report['files'][relative] = {'sha256': digest.hexdigest(),
                                   'bytes': target.stat().st_size,
                                   'original_mode': stat.S_IMODE(before.st_mode)}

    for name in SOURCES:
        path = source / name
        if not path.exists():
            if name in ('infrastructure', 'secrets'):
                raise FileNotFoundError('Required configuration directory: '+name)
            report['excluded'][name] = 'not_present'
            continue
        walk(path)
    if 'secrets/postgres_password' not in report['files']:
        raise RuntimeError('Required PostgreSQL restore credential absent')
    return report


if __name__ == '__main__':
    os.umask(0o077)
    print(json.dumps(collect('/source', '/snapshot')))
