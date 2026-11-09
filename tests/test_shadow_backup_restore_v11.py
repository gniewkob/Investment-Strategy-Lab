"""Offline v0.11 snapshot and restore drills using disposable SQLite only."""
from pathlib import Path
import os
import sqlite3
import stat
import tempfile
import unittest

from scripts.shadow_backup_restore_v11 import (
    create_snapshot, restore_drill, verify_snapshot,
)
from scripts.shadow_decision_engine_v05 import ShadowInputError
from scripts.shadow_evidence_ledger_v09 import append, audit
from scripts.shadow_external_anchor_v10 import prepare_anchor, write_new_anchor
from tests.test_shadow_evidence_ledger_v09 import valid_bundle


class SnapshotV11Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ledger = self.root / "ledger.sqlite3"
        self.anchors = self.root / "anchors"
        self.backups = self.root / "backups"
        self.restores = self.root / "restore-tests"
        for d in (self.anchors, self.backups, self.restores):
            d.mkdir(mode=0o700)
        append(self.ledger, valid_bundle())
        anchor = prepare_anchor(self.ledger, created_at_utc="2026-11-06T22:40:00Z")
        self.anchored = write_new_anchor(self.anchors, anchor)

    def backup(self):
        return create_snapshot(self.ledger, self.anchored["path"],
                               self.anchored["anchor_sha256"], self.backups)

    def test_verified_backup_and_restore_keep_source_untouched(self):
        old = audit(self.ledger)
        result = self.backup()
        self.assertEqual(result["status"], "LOCAL_SNAPSHOT_VERIFIED_NOT_OFFSITE")
        self.assertEqual(result["current_entries"], 1)
        self.assertFalse(result["offsite_verified"])
        verify = verify_snapshot(result["path"], result["manifest_sha256"])
        self.assertEqual(verify["anchored_head_sha256"], old["head_sha256"])
        restored = restore_drill(result["path"], result["manifest_sha256"], self.restores)
        self.assertEqual(restored["status"], "RESTORE_VERIFIED_NOT_ACTIVATED")
        self.assertEqual(verify_snapshot(restored["path"], result["manifest_sha256"]), verify)
        self.assertEqual(audit(self.ledger), old)
        self.assertEqual(len(list(self.backups.iterdir())), 1)
        self.assertEqual(len(list(self.restores.iterdir())), 1)
        self.assertEqual(result["financial_operations"], 0)

    def test_manifest_pin_cannot_be_inferred_from_manifest_itself(self):
        result = self.backup()
        with self.assertRaisesRegex(ShadowInputError, "manifest pin mismatch"):
            verify_snapshot(result["path"], "0" * 64)
        with self.assertRaisesRegex(ShadowInputError, "supplied manifest"):
            restore_drill(result["path"], None, self.restores)

    def test_changed_snapshot_fails_even_if_original_is_healthy(self):
        result = self.backup()
        db = Path(result["path"]) / "ledger.sqlite3"
        with sqlite3.connect(db) as conn:
            conn.execute("DROP TRIGGER evidence_no_update")
            conn.execute("UPDATE evidence SET entry_sha256='tampered' WHERE seq=1")
        with self.assertRaisesRegex(ShadowInputError, "snapshot file digest mismatch"):
            verify_snapshot(result["path"], result["manifest_sha256"])
        self.assertEqual(audit(self.ledger)["entries"], 1)

    def test_wrong_anchor_pin_fails_before_backup(self):
        with self.assertRaisesRegex(ShadowInputError, "independent pinned value"):
            create_snapshot(self.ledger, self.anchored["path"], "a" * 64, self.backups)
        self.assertEqual(list(self.backups.iterdir()), [])

    def test_non_private_destination_is_rejected(self):
        os.chmod(self.backups, 0o755)
        with self.assertRaisesRegex(ShadowInputError, "permissions 0700"):
            self.backup()

    def test_symlink_snapshot_is_rejected(self):
        result = self.backup()
        alias = self.root / "alias"
        try:
            alias.symlink_to(result["path"], target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not supported")
        with self.assertRaisesRegex(ShadowInputError, "private directory"):
            verify_snapshot(alias, result["manifest_sha256"])

    def test_restore_never_overwrites_existing_data(self):
        result = self.backup()
        existing = self.restores / "active.sqlite3"
        existing.write_text("do-not-replace")
        restore_drill(result["path"], result["manifest_sha256"], self.restores)
        self.assertEqual(existing.read_text(), "do-not-replace")

    def test_anchor_blocks_truncated_source(self):
        append(self.ledger, valid_bundle(42303069320, 1234568))
        newer = prepare_anchor(self.ledger, created_at_utc="2026-11-06T22:40:00Z")
        anchor = write_new_anchor(self.anchors, newer)
        with sqlite3.connect(self.ledger) as conn:
            conn.execute("DROP TRIGGER evidence_no_delete")
            conn.execute("DELETE FROM evidence WHERE seq=2")
        with self.assertRaisesRegex(ShadowInputError, "truncated"):
            create_snapshot(self.ledger, anchor["path"], anchor["anchor_sha256"], self.backups)


if __name__ == "__main__":
    unittest.main()
