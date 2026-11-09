"""Synthetic-only security regressions for inventory audit, no external access."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.provider_workflow_review_v01 import (
    InventoryError, audit, git_blob_sha1, observed_signals, read_inventory
)

MANIFEST = Path(__file__).resolve().parents[1] / "governance/isl_provider_workflow_inventory_v01.json"


class ProviderWorkflowReviewTests(unittest.TestCase):
    def setUp(self):
        self.data = read_inventory(MANIFEST)

    def test_actual_manifest_has_16_unique_hold_only_workflows(self):
        self.assertEqual(self.data["count"], 16)
        self.assertEqual(len({r["path"] for r in self.data["workflows"]}), 16)
        self.assertEqual(self.data["authorization"], "NOT_GRANTED")
        self.assertEqual({r["approval"] for r in self.data["workflows"]}, {"HOLD_FOR_SEPARATE_REVIEW"})

    def test_absent_code_is_not_approved_or_attested(self):
        with TemporaryDirectory() as tmp:
            r = audit(tmp, self.data)
            self.assertEqual(r["missing_count"], 16)
            self.assertEqual(r["present_count"], 0)
            self.assertEqual(r["status"], "SOURCE_REVIEW_REQUIRED")
            self.assertFalse(r["activation_approved"])
            self.assertFalse(r["provider_rights_verified"])
            self.assertEqual(r["financial_operations"], 0)

    def test_strict_mode_fails_closed_when_original_source_files_absent(self):
        with TemporaryDirectory() as tmp:
            r = audit(tmp, self.data, require_all=True)
            self.assertEqual(r["status"], "SNAPSHOT_INCOMPLETE_OR_CHANGED")

    def test_matching_git_blob_still_not_authorized(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = self.data["workflows"][0]
            p = root / row["path"]
            p.parent.mkdir(parents=True)
            contents = b"name: Synthetic\non:\n  workflow_dispatch:\n"
            p.write_bytes(contents)
            manifest = deepcopy(self.data)
            manifest["workflows"][0]["git_blob_sha1"] = git_blob_sha1(contents)
            r = audit(root, manifest)
            self.assertEqual(r["present_count"], 1)
            self.assertEqual(r["changed_count"], 0)
            self.assertEqual(r["items"][0]["status"], "EXACT_SOURCE_BLOB_FOR_REVIEW_ONLY")
            self.assertFalse(r["activation_approved"])

    def test_change_detected_even_with_passing_synthetic_workflow(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = self.data["workflows"][0]
            p = root / row["path"]
            p.parent.mkdir(parents=True)
            p.write_text("name: mutated\non:\n  schedule:\n    - cron: '0 0 * * *'\n")
            r = audit(root, self.data)
            self.assertEqual(r["status"], "SNAPSHOT_INCOMPLETE_OR_CHANGED")
            self.assertEqual(r["changed_count"], 1)
            self.assertTrue(r["items"][0]["observed_signals"]["schedule_literal"])

    def test_invalid_manifest_cannot_override_review_hold(self):
        bad = deepcopy(self.data)
        bad["authorization"] = "GRANTED"
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "manifest.json"
            p.write_text(json.dumps(bad))
            with self.assertRaisesRegex(InventoryError, "no provider activation"):
                read_inventory(p)

    def test_duplicate_path_cannot_hide_unreviewed_source(self):
        bad = deepcopy(self.data)
        bad["workflows"][1]["path"] = bad["workflows"][0]["path"]
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "manifest.json"
            p.write_text(json.dumps(bad))
            with self.assertRaisesRegex(InventoryError, "duplicate"):
                read_inventory(p)

    def test_source_outside_checkout_symlink_rejected(self):
        with TemporaryDirectory() as root_dir, TemporaryDirectory() as outside:
            root = Path(root_dir)
            row = self.data["workflows"][0]
            link = root / row["path"]
            link.parent.mkdir(parents=True)
            link.symlink_to(Path(outside)/"outside.yml")
            with self.assertRaisesRegex(InventoryError, "escapes"):
                audit(root, self.data)

    def test_signal_scanner_is_advisory_not_yaml_security_parser(self):
        s = ("name: synthetic\non:\n  workflow_dispatch:\n  schedule:\n"
             "    - cron: '17 6 * * 1'\njobs:\n  test:\n    steps:\n"
             "      - uses: actions/checkout@v4\n"
             "      - uses: actions/upload-artifact@v4\n")
        flags = observed_signals(s)
        self.assertTrue(flags["schedule_literal"])
        self.assertTrue(flags["artifact_upload_literal"])
        self.assertTrue(flags["manual_dispatch_literal"])
        self.assertTrue(flags["checkout_literal"])
        self.assertFalse(flags["persist_credentials_false_literal"])


    def test_governance_mode_rejects_exact_original_blob_without_approval(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = self.data["workflows"][0]
            p = root / row["path"]
            p.parent.mkdir(parents=True)
            contents = b"name: fixture\\non:\\n  workflow_dispatch:\\n"
            p.write_bytes(contents)
            manifest = deepcopy(self.data)
            manifest["workflows"][0]["git_blob_sha1"] = git_blob_sha1(contents)
            result = audit(root, manifest, forbid_present=True)
            self.assertEqual(result["status"], "QUARANTINED_WORKFLOW_PRESENT")
            self.assertEqual(result["present_count"], 1)
            self.assertEqual(result["changed_count"], 0)
            self.assertFalse(result["activation_approved"])
            self.assertEqual(result["financial_operations"], 0)

    def test_governance_mode_succeeds_only_with_all_16_absent(self):
        with TemporaryDirectory() as tmp:
            result = audit(tmp, self.data, forbid_present=True)
            self.assertEqual(result["status"], "SOURCE_REVIEW_REQUIRED")
            self.assertEqual(result["missing_count"], 16)
            self.assertEqual(result["present_count"], 0)

    def test_conflicting_audit_modes_are_rejected(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(InventoryError, "mutually exclusive"):
                audit(tmp, self.data, require_all=True, forbid_present=True)

    def test_governance_ci_triggers_on_workflows_and_uses_strict_mode(self):
        ci = (Path(__file__).resolve().parents[1] /
              ".github/workflows/isl-source-governance-g1-ci.yml").read_text(encoding="utf-8")
        self.assertIn("- '.github/workflows/**'", ci)
        self.assertIn("--forbid-present", ci)
        self.assertIn("assert record['present_count']==0", ci)


if __name__ == "__main__":
    unittest.main()
