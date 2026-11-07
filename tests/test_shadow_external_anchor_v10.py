"""Isolated v0.10 external-head checks: no network, account or Neon access."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.shadow_decision_engine_v05 import ShadowInputError
from scripts.shadow_evidence_ledger_v09 import append, audit
from scripts.shadow_external_anchor_v10 import (
    prepare_anchor, write_new_anchor, verify_anchor, _canonical_bytes,
)
from tests.test_shadow_evidence_ledger_v09 import valid_bundle


class ExternalAnchorV10Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.ledger = root / "evidence.sqlite"
        self.anchor_dir = root / "independently_retained_copy"
        self.anchor_dir.mkdir()
        append(self.ledger, valid_bundle())

    def _anchor(self):
        snapshot = prepare_anchor(self.ledger, created_at_utc="2026-11-06T22:40:00Z")
        result = write_new_anchor(self.anchor_dir, snapshot)
        return snapshot, Path(result["path"]), result["anchor_sha256"]

    def test_anchor_matches_verified_one_entry_ledger(self):
        entry, path, digest = self._anchor()
        result = verify_anchor(self.ledger, path, expected_sha256=digest)
        self.assertEqual(result["status"], "SUPPLIED_HASH_AND_SQLITE_PREFIX_MATCH_NOT_EXTERNAL_PROOF")
        self.assertEqual(result["anchored_entries"], 1)
        self.assertEqual(result["current_entries"], 1)
        self.assertEqual(result["anchored_head_sha256"], audit(self.ledger)["head_sha256"])
        self.assertEqual(sha256(path.read_bytes()).hexdigest(), digest)
        self.assertEqual(path.read_bytes(), _canonical_bytes(entry))
        self.assertFalse(result["trusted_time_verified"])
        self.assertFalse(result["external_hash_independently_witnessed"])
        self.assertFalse(result["external_WORM_storage_verified"])
        self.assertEqual(result["financial_operations"], 0)

    def test_prior_anchor_still_checks_prefix_after_later_append(self):
        _, path, digest = self._anchor()
        append(self.ledger, valid_bundle(42303069320, 1234568))
        result = verify_anchor(self.ledger, path, expected_sha256=digest)
        self.assertEqual(result["anchored_entries"], 1)
        self.assertEqual(result["current_entries"], 2)
        self.assertNotEqual(result["anchored_head_sha256"], result["current_head_sha256"])

    def test_externally_pinned_anchor_detects_tail_truncation(self):
        append(self.ledger, valid_bundle(42303069320, 1234568))
        _, path, digest = self._anchor()
        with sqlite3.connect(self.ledger) as conn:
            conn.execute("DROP TRIGGER evidence_no_delete")
            conn.execute("DELETE FROM evidence WHERE seq=2")
        with self.assertRaisesRegex(ShadowInputError, "truncated"):
            verify_anchor(self.ledger, path, expected_sha256=digest)

    def test_forged_anchor_rejected_even_with_self_consistent_digest(self):
        _, path, pinned = self._anchor()
        anchor = json.loads(path.read_text())
        anchor["entries"] = 999
        path.write_bytes(_canonical_bytes(anchor))
        with self.assertRaisesRegex(ShadowInputError, "independent pinned value"):
            verify_anchor(self.ledger, path, expected_sha256=pinned)

    def test_changed_ledger_history_detected(self):
        _, path, digest = self._anchor()
        with sqlite3.connect(self.ledger) as conn:
            conn.execute("DROP TRIGGER evidence_no_update")
            conn.execute("UPDATE evidence SET entry_sha256='bad' WHERE seq=1")
        with self.assertRaisesRegex(ShadowInputError, "ledger chain hash mismatch"):
            verify_anchor(self.ledger, path, expected_sha256=digest)

    def test_anchor_never_overwrites_existing_file(self):
        entry, path, digest = self._anchor()
        original = path.read_bytes()
        with self.assertRaisesRegex(ShadowInputError, "cannot be overwritten"):
            write_new_anchor(self.anchor_dir, entry)
        self.assertEqual(original, path.read_bytes())
        self.assertEqual(digest, sha256(path.read_bytes()).hexdigest())

    def test_missing_pinned_checksum_fails_closed(self):
        _, path, _ = self._anchor()
        with self.assertRaisesRegex(ShadowInputError, "independently pinned"):
            verify_anchor(self.ledger, path, expected_sha256=None)
        with self.assertRaisesRegex(ShadowInputError, "independently pinned"):
            verify_anchor(self.ledger, path, expected_sha256="abc")

    def test_declared_authority_and_future_time_rejected(self):
        with self.assertRaisesRegex(ShadowInputError, "in the future"):
            prepare_anchor(self.ledger, created_at_utc="2099-01-01T00:00:00Z")
        a = prepare_anchor(self.ledger, created_at_utc="2026-11-06T22:40:00Z")
        a["time_independently_attested"] = True
        with self.assertRaisesRegex(ShadowInputError, "unverified authority"):
            write_new_anchor(self.anchor_dir, a)

    def test_never_anchor_empty_or_missing_ledger(self):
        with self.assertRaisesRegex(ShadowInputError, "ledger does not exist"):
            prepare_anchor(Path(self.temp.name) / "missing.sqlite",
                           created_at_utc="2026-11-06T22:40:00Z")

    def test_anchor_dir_not_implicitly_created(self):
        a = prepare_anchor(self.ledger, created_at_utc="2026-11-06T22:40:00Z")
        with self.assertRaisesRegex(ShadowInputError, "must already exist"):
            write_new_anchor(Path(self.temp.name) / "not_a_directory", a)


if __name__ == "__main__":
    unittest.main()
