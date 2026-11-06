"""Disposable local SQLite integrity suite; no real trading or Neon I/O."""
from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.github_checkpoint_verify_v08 import verify
from scripts.shadow_decision_engine_v05 import ShadowInputError, _digest
from scripts.shadow_evidence_ledger_v09 import append, audit, GENESIS
from tests.test_github_checkpoint_verify_v08 import scenario, CUTOFF


def valid_bundle(run_id=None, artifact_id=None):
    capture, run, artifacts = scenario()
    if run_id is not None:
        capture["run_context_declared"]["run_id"] = run_id
        capture["capture_sha256"] = _digest({
            k: v for k, v in capture.items() if k != "capture_sha256"
        })
        run["id"] = run_id
        artifacts["artifacts"][0]["workflow_run"]["id"] = run_id
        artifacts["artifacts"][0]["name"] = (
            f"isl-v07-shadow-capture-run-{run_id}-attempt-1"
        )
    if artifact_id is not None:
        artifacts["artifacts"][0]["id"] = artifact_id
    checkpoint = verify(capture, run, artifacts, cutoff_utc=CUTOFF)
    checkpoint["receipt_sha256"] = _digest(checkpoint)
    return {"capture": capture, "run": run, "artifacts": artifacts,
            "checkpoint": checkpoint}


class ShadowEvidenceLedgerV09Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "isolated" / "evidence.sqlite3"

    def test_two_persistent_records_and_independent_read_only_replay(self):
        one = valid_bundle()
        two = valid_bundle(42303069320, 1234568)
        first = append(self.db, one)
        self.assertEqual(first["append_status"], "NEW_EVIDENCE")
        self.assertEqual(first["entries"], 1)
        self.assertNotEqual(first["head_sha256"], GENESIS)
        second = append(self.db, two)
        self.assertEqual(second["entries"], 2)
        self.assertEqual(audit(self.db)["head_sha256"], second["head_sha256"])
        replay = append(self.db, deepcopy(one))
        self.assertEqual(replay["append_status"], "IDEMPOTENT_REPLAY")
        self.assertEqual(replay["entries"], 2)

    def test_duplicate_identity_with_changed_payload_is_rejected(self):
        one = valid_bundle()
        append(self.db, one)
        changed = deepcopy(one)
        changed["run"]["extra_untrusted_field"] = "different"
        with self.assertRaisesRegex(ShadowInputError, "conflicting evidence"):
            append(self.db, changed)
        self.assertEqual(audit(self.db)["entries"], 1)

    def test_invalid_checkpoint_and_modified_capture_fail_closed(self):
        bundle = valid_bundle()
        bundle["checkpoint"]["orders_sent"] = 1
        with self.assertRaisesRegex(ShadowInputError, "receipt SHA mismatch"):
            append(self.db, bundle)
        bundle = valid_bundle()
        bundle["capture"]["captured_at_utc"] = "2026-11-05T00:00:00Z"
        with self.assertRaisesRegex(ShadowInputError, "capture content fingerprint mismatch"):
            append(self.db, bundle)
        self.assertFalse(self.db.exists())

    def test_trigger_rejects_sql_update_delete(self):
        append(self.db, valid_bundle())
        with sqlite3.connect(self.db) as conn:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only evidence"):
                conn.execute("UPDATE evidence SET bundle_sha256='fake' WHERE seq=1")
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only evidence"):
                conn.execute("DELETE FROM evidence WHERE seq=1")
        self.assertEqual(audit(self.db)["entries"], 1)

    def test_out_of_band_tampering_is_detected_when_reopened(self):
        append(self.db, valid_bundle())
        with sqlite3.connect(self.db) as conn:
            conn.execute("DROP TRIGGER evidence_no_update")
            conn.execute("UPDATE evidence SET previous_sha256='bad' WHERE seq=1")
        with self.assertRaisesRegex(ShadowInputError, "previous hash corrupted"):
            audit(self.db)
        with self.assertRaisesRegex(ShadowInputError, "previous hash corrupted"):
            append(self.db, valid_bundle(42303069320, 1234568))

    def test_uninitialized_or_absent_ledger_not_accepted_as_evidence(self):
        with self.assertRaisesRegex(ShadowInputError, "ledger does not exist"):
            audit(self.db)


if __name__ == "__main__":
    unittest.main()
