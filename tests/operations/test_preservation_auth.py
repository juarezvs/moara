import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[2]/'moara/infrastructure/scripts/preservation.py'

class PreservationAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for folder in ['infrastructure','secrets','backups']:(self.root/folder).mkdir()
        (self.root/'infrastructure/.env').write_text('PYTHON_IMAGE=synthetic\nPOSTGRES_IMAGE=synthetic\n')
        (self.root/'secrets/backup_key').write_bytes(b'synthetic-key-for-tests-only')
        with patch.dict(os.environ,{'MOARA_PRESERVATION_ROOT':str(self.root)}):
            spec=importlib.util.spec_from_file_location('preservation_test',SCRIPT)
            self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        self.backup=self.root/'backups/moara-before-migration-synthetic.tar.enc'
        self.backup.write_bytes(b'synthetic encrypted bytes')
        self.backup.with_suffix('.enc.hmac').write_text(self.module.authenticate(self.backup))

    def test_changed_ciphertext_rejected_before_decryption(self):
        self.backup.write_bytes(b'tampered encrypted bytes')
        with patch.object(self.module,'run') as run:
            with self.assertRaisesRegex(ValueError,'authentication failed'):
                self.module.verify(self.backup)
            run.assert_not_called()

    def test_invalid_hmac_rejected_before_decryption(self):
        self.backup.with_suffix('.enc.hmac').write_text('0'*64)
        with patch.object(self.module,'run') as run:
            with self.assertRaisesRegex(ValueError,'authentication failed'):
                self.module.verify(self.backup)
            run.assert_not_called()

    def test_restore_outside_backup_directory_rejected(self):
        outside=self.root/'moara-before-migration-external.tar.enc'
        outside.write_bytes(b'synthetic')
        with patch.object(self.module,'run') as run:
            with self.assertRaisesRegex(ValueError,'preservation file'):
                self.module.verify(outside)
            run.assert_not_called()

if __name__=='__main__':unittest.main()
