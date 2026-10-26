import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / 'moara/infrastructure/scripts/config_snapshot.py'
spec = importlib.util.spec_from_file_location('config_snapshot', SCRIPT)
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)

class ConfigurationSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'source'
        self.target = Path(self.temp.name) / 'snapshot'
        for name in ('infrastructure', 'secrets'):
            (self.source/name).mkdir(parents=True)
        (self.source/'secrets/postgres_password').write_text('synthetic-only')
        (self.source/'secrets/backup_key').write_text('excluded-synthetic-key')
        (self.source/'infrastructure/app.txt').write_text('fixture')

    def collect(self):
        return snapshot.collect(self.source, self.target)

    def test_configuration_excludes_key_and_dependencies(self):
        (self.source/'infrastructure/node_modules').mkdir()
        (self.source/'infrastructure/node_modules/ignored').write_text('cache')
        report = self.collect()
        self.assertEqual((self.target/'secrets/postgres_password').read_text(), 'synthetic-only')
        self.assertFalse((self.target/'secrets/backup_key').exists())
        self.assertFalse((self.target/'infrastructure/node_modules').exists())
        self.assertNotIn('synthetic-only', json.dumps(report))
        self.assertEqual(len(report['files']['secrets/postgres_password']['sha256']),64)

    def test_permission_denial_is_fatal(self):
        original_open = os.open
        def protected_open(path, flags, *args, **kwargs):
            if isinstance(path, (str, Path)) and Path(path).name == 'postgres_password':
                raise PermissionError('synthetic denied')
            return original_open(path, flags, *args, **kwargs)
        with patch.object(snapshot.os, 'open', side_effect=protected_open):
            with self.assertRaises(PermissionError):
                self.collect()

    def test_missing_restore_credential_is_fatal(self):
        (self.source/'secrets/postgres_password').unlink()
        with self.assertRaisesRegex(RuntimeError, 'credential absent'):
            self.collect()

    def test_changed_file_is_fatal(self):
        original_copy = shutil.copyfileobj
        def mutate(source, dest, length):
            original_copy(source, dest, length)
            with (self.source/'infrastructure/app.txt').open('ab') as stream:
                stream.write(b'changed')
        with patch.object(snapshot.shutil, 'copyfileobj', side_effect=mutate):
            with self.assertRaisesRegex(RuntimeError, 'changed during preservation'):
                self.collect()

    def test_symlinks_rejected(self):
        link = self.source/'infrastructure/link'
        try:
            link.symlink_to(self.source/'secrets/postgres_password')
        except OSError:
            self.skipTest('Symlink privilege unavailable')
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            self.collect()

if __name__ == '__main__':
    unittest.main()
