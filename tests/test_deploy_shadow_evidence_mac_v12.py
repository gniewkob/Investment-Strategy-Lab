"""Deployment v0.12 must never mutate an existing Mac installation."""
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from scripts import deploy_shadow_evidence_mac_v12 as installer

from scripts.deploy_shadow_evidence_mac_v12 import deploy_isolated
from scripts.shadow_decision_engine_v05 import ShadowInputError
from scripts.shadow_evidence_ledger_v09 import audit
from scripts.shadow_external_anchor_v10 import verify_anchor
from scripts.shadow_backup_restore_v11 import verify_snapshot
from tests.test_shadow_evidence_ledger_v09 import valid_bundle


class MacShadowDeployV12Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self.root / "unique-new-shadow-study"
        self.bundle = valid_bundle()
        self.original_bundle = json.dumps(self.bundle, sort_keys=True)

    def test_isolated_install_retains_anchor_backup_restore_without_live_access(self):
        done = deploy_isolated(self.target, self.bundle, source_sha="a" * 40)
        self.assertEqual(done["status"], "ISOLATED_RESEARCH_LEDGER_DEPLOYED_NO_SCHEDULE")
        self.assertEqual(done["entries"], 1)
        self.assertEqual(done["financial_operations"], 0)
        self.assertFalse(done["active_scheduler_changed"])
        self.assertFalse(done["neon_modified"])
        self.assertFalse(done["offsite_backup_verified"])
        ledger = self.target / done["ledger_relpath"]
        anchor = self.target / done["anchor_relpath"]
        self.assertEqual(audit(ledger)["head_sha256"], done["head_sha256"])
        self.assertEqual(
            verify_anchor(ledger, anchor, expected_sha256=done["anchor_sha256"])["anchored_entries"], 1
        )
        snap = verify_snapshot(self.target / done["backup_relpath"], done["backup_manifest_sha256"])
        restored = verify_snapshot(self.target / done["restore_relpath"], done["backup_manifest_sha256"])
        self.assertEqual(snap, restored)
        self.assertEqual(done["head_sha256"], restored["anchored_head_sha256"])
        self.assertEqual(stat.S_IMODE(ledger.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o700)
        recorded = json.loads((self.target / "state" / "deployment-receipt-v12.json").read_text())
        self.assertEqual(recorded["head_sha256"], done["head_sha256"])
        self.assertEqual(json.dumps(self.bundle, sort_keys=True), self.original_bundle)

    def test_source_preflight_rejects_modified_and_untracked_checkout(self):
        # Mock the Git metadata; never interact with a real Mac or installer.
        repo_root = Path(installer.__file__).resolve().parents[1]
        for working_tree in (
            " M scripts/shadow_evidence_ledger_v09.py\\n",
            "?? scripts/new_unreviewed_helper.py\\n",
        ):
            with self.subTest(status=working_tree):
                answers = ["a" * 40, "https://github.com/" + installer.REPOSITORY,
                           working_tree]
                with patch.object(installer.os, "geteuid", return_value=1000), \
                     patch.object(installer.subprocess, "check_output",
                                  side_effect=answers):
                    with self.assertRaisesRegex(ShadowInputError, "must be clean"):
                        installer.preflight(repo_root, self.target, "a" * 40,
                                            require_macos=False)
                self.assertFalse(self.target.exists())

    def test_source_preflight_accepts_clean_exact_checkout(self):
        repo_root = Path(installer.__file__).resolve().parents[1]
        answers = ["a" * 40, "https://github.com/" + installer.REPOSITORY, ""]
        with patch.object(installer.os, "geteuid", return_value=1000), \
             patch.object(installer.subprocess, "check_output",
                          side_effect=answers):
            evidence = installer.preflight(
                repo_root, self.target, "a" * 40, require_macos=False)
        self.assertIsInstance(evidence, dict)
        self.assertFalse(self.target.exists())

    def test_no_redeploy_when_target_already_exists(self):
        before = self.target.mkdir()
        keep = self.target / "existing-important-document.txt"
        keep.write_text("do not touch")
        with self.assertRaisesRegex(ShadowInputError, "target already exists"):
            deploy_isolated(self.target, self.bundle, source_sha="a" * 40)
        self.assertEqual(keep.read_text(), "do not touch")

    def test_invalid_bundle_fails_without_new_target_or_leftover_staging(self):
        bad = dict(self.bundle)
        bad["checkpoint"] = dict(bad["checkpoint"])
        bad["checkpoint"]["orders_sent"] = 1
        with self.assertRaisesRegex(ShadowInputError, "receipt SHA mismatch"):
            deploy_isolated(self.target, bad, source_sha="a" * 40)
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_unexpected_existing_destination_symlink_rejected(self):
        referent = self.root / "unrelated"
        referent.mkdir()
        self.target.symlink_to(referent, target_is_directory=True)
        with self.assertRaisesRegex(ShadowInputError, "target already exists"):
            deploy_isolated(self.target, self.bundle, source_sha="a" * 40)
        self.assertEqual(list(referent.iterdir()), [])

    def test_existing_private_tree_is_not_modified_during_refusal(self):
        self.target.mkdir(mode=0o700)
        (self.target / "ledger").mkdir(mode=0o700)
        (self.target / "ledger" / "working.sqlite3").write_bytes(b"unchanged")
        with self.assertRaisesRegex(ShadowInputError, "target already exists"):
            deploy_isolated(self.target, self.bundle, source_sha="a" * 40)
        self.assertEqual((self.target / "ledger" / "working.sqlite3").read_bytes(), b"unchanged")


if __name__ == "__main__":
    unittest.main()
