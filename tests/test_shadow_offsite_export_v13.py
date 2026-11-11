"""v0.13 local copy test suite: isolated, no external services or financial actions."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from scripts.shadow_decision_engine_v05 import ShadowInputError
from scripts.shadow_offsite_export_v13 import export_copy, verify_export
from scripts.shadow_backup_restore_v11 import create_snapshot, restore_drill
from scripts.shadow_evidence_ledger_v09 import append
from scripts.shadow_external_anchor_v10 import prepare_anchor, write_new_anchor
from tests.test_shadow_evidence_ledger_v09 import valid_bundle


class V13CopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.anchors = self.root / "anchors"
        self.backups = self.root / "backups"
        self.destination = self.root / "destination"
        self.restore = self.root / "restore"
        for folder in (self.anchors, self.backups, self.destination, self.restore):
            folder.mkdir(mode=0o700)
        self.ledger = self.root / "ledger.sqlite3"
        append(self.ledger, valid_bundle())
        anchor = prepare_anchor(self.ledger, created_at_utc="2026-11-06T22:40:00Z")
        written = write_new_anchor(self.anchors, anchor)
        self.snapshot = create_snapshot(
            self.ledger, written["path"], written["anchor_sha256"], self.backups)
        self.pin = self.snapshot["manifest_sha256"]

    def export(self, name="separate-copy-01"):
        return export_copy(self.snapshot["path"], self.pin, self.destination, name=name)

    def test_oversize_manifest_rejected_before_unbounded_verifier(self):
        from scripts import shadow_offsite_export_v13 as module
        manifest = Path(self.snapshot["path"]) / "manifest.json"
        with manifest.open("ab") as out:
            out.write(b"x" * (64 * 1024 + 1))
        with patch.object(module, "verify_snapshot",
                          side_effect=AssertionError("unbounded verifier reached")):
            with self.assertRaisesRegex(ShadowInputError, "bounded"):
                self.export()
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_oversize_ledger_rejected_before_unbounded_verifier(self):
        from scripts import shadow_offsite_export_v13 as module
        snap = Path(self.snapshot["path"])
        manifest_bytes = (snap / "manifest.json").stat().st_size
        ledger_bytes = (snap / "ledger.sqlite3").stat().st_size
        self.assertGreater(ledger_bytes, manifest_bytes + 1)
        with patch.object(module, "MAX_FILE_BYTES", manifest_bytes + 1), \
             patch.object(module, "verify_snapshot",
                          side_effect=AssertionError("unbounded verifier reached")):
            with self.assertRaisesRegex(ShadowInputError, "bounded"):
                self.export()
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_symlink_source_rejected_before_unbounded_verifier(self):
        from scripts import shadow_offsite_export_v13 as module
        anchor = Path(self.snapshot["path"]) / "anchor.json"
        target = self.root / "same-anchor.json"
        target.write_bytes(anchor.read_bytes())
        anchor.unlink()
        anchor.symlink_to(target)
        with patch.object(module, "verify_snapshot",
                          side_effect=AssertionError("unbounded verifier reached")):
            with self.assertRaises(OSError):
                self.export()
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_export_readback_and_restore_drill(self):
        result = self.export()
        self.assertEqual(result["status"], "COPY_READBACK_VERIFIED_FAILURE_DOMAIN_UNVERIFIED")
        self.assertEqual(result["entries"], 1)
        self.assertFalse(result["independent_failure_domain_verified"])
        self.assertFalse(result["offsite_verified"])
        self.assertEqual(result["financial_operations"], 0)
        verified = verify_export(self.destination, "separate-copy-01", self.pin)
        self.assertEqual(verified["manifest_sha256"], self.pin)
        restored = restore_drill(self.destination / "separate-copy-01", self.pin, self.restore)
        self.assertEqual(restored["status"], "RESTORE_VERIFIED_NOT_ACTIVATED")

    def test_refuse_duplicate_and_preserve_original(self):
        self.export()
        unchanged = (self.destination / "separate-copy-01" / "manifest.json").read_bytes()
        with self.assertRaisesRegex(ShadowInputError, "never overwrite"):
            self.export()
        self.assertEqual((self.destination / "separate-copy-01" / "manifest.json").read_bytes(), unchanged)

    def test_refuse_symlink_destination(self):
        alias = self.root / "alias"
        alias.symlink_to(self.destination, target_is_directory=True)
        with self.assertRaisesRegex(ShadowInputError, "non-symlink"):
            export_copy(self.snapshot["path"], self.pin, alias, name="do-not-write")
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_refuse_symlink_export(self):
        (self.destination / "separate-copy-01").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ShadowInputError, "never overwrite"):
            self.export()
        with self.assertRaises(OSError):
            verify_export(self.destination, "separate-copy-01", self.pin)

    def test_refuse_public_destination(self):
        os.chmod(self.destination, 0o755)
        with self.assertRaisesRegex(ShadowInputError, "0700"):
            self.export()

    def test_invalid_name_and_missing_manifest_pin(self):
        for name in ("../escape", "a/b", ".", "some name"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ShadowInputError, "invalid export name"):
                    self.export(name=name)
        with self.assertRaisesRegex(ShadowInputError, "source digest|manifest pin"):
            export_copy(self.snapshot["path"], "0" * 64, self.destination, name="invalidpin")

    def test_detect_tampered_export(self):
        self.export()
        with sqlite3.connect(self.destination / "separate-copy-01" / "ledger.sqlite3") as conn:
            conn.execute("DROP TRIGGER evidence_no_update")
            conn.execute("UPDATE evidence SET entry_sha256='fake' WHERE seq=1")
        with self.assertRaisesRegex(ShadowInputError, "sha256 mismatch"):
            verify_export(self.destination, "separate-copy-01", self.pin)

    def test_detect_file_symlink_in_copied_directory(self):
        self.export()
        folder = self.destination / "separate-copy-01"
        (folder / "anchor.json").unlink()
        (folder / "anchor.json").symlink_to(str(self.snapshot["path"]) + "/anchor.json")
        with self.assertRaises(OSError):
            verify_export(self.destination, "separate-copy-01", self.pin)

    def test_changed_source_fails_before_any_export(self):
        with sqlite3.connect(Path(self.snapshot["path"]) / "ledger.sqlite3") as conn:
            conn.execute("DROP TRIGGER evidence_no_update")
            conn.execute("UPDATE evidence SET entry_sha256='fake' WHERE seq=1")
        with self.assertRaisesRegex(ShadowInputError, "digest mismatch"):
            self.export()
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_fail_closed_if_root_is_swapped_during_copy(self):
        from scripts import shadow_offsite_export_v13 as module
        original = module._read_source
        moved = self.root / "displaced"
        first = [True]

        def interfere(*args, **kwargs):
            if first[0]:
                first[0] = False
                self.destination.rename(moved)
                self.destination.mkdir(mode=0o700)
            return original(*args, **kwargs)

        with patch.object(module, "_read_source", side_effect=interfere):
            with self.assertRaisesRegex(ShadowInputError, "path was swapped"):
                self.export()
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_refuse_copy_into_source_snapshot(self):
        # Source snapshot itself is 0700, but must not contain the export.
        with self.assertRaisesRegex(ShadowInputError, "inside snapshot"):
            export_copy(self.snapshot["path"], self.pin, self.snapshot["path"], name="bad")


if __name__ == "__main__":
    unittest.main()
