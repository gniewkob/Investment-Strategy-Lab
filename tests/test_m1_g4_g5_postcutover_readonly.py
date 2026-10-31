"""Offline tests for post-G3 read-only G4 and G5 acceptance boundaries."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import m1_g4_g5_postcutover_readonly as m


class G4G5ReadOnlyTests(unittest.TestCase):
    CUTOVER = 1000.0

    def rows(self, count, *, pre_g3=0):
        rows = []
        for i in range(-pre_g3, count):
            observed = self.CUTOVER + 60 * (i + 1)
            checkpoint = (self.CUTOVER + 900 * ((i + 1) // 15)
                          if i >= 14 else self.CUTOVER - 300)
            rows.append({
                "observed_at": observed,
                "checkpoint_at": checkpoint,
                "status": "OBSERVATION_OK",
                "financial_operations": 0,
                "http_429_count": 0,
                "runtime": {
                    "unique_natural_supervisor": True,
                    "pid": 1324,
                    "process_start": "constant-start",
                    "launchagent_hashes": ["supervisor-sha", "watchdog-sha"],
                },
            })
        return rows

    def assess(self, rows, *, age=20):
        now = (rows[-1]["observed_at"] + age
               if rows else self.CUTOVER + age)
        with patch.object(m.acceptance, "healthy",
                          side_effect=lambda r: r["status"] == "OBSERVATION_OK"):
            return m.evaluate(rows, self.CUTOVER, now)

    def test_one_natural_checkpoint_remains_pending(self):
        result = self.assess(self.rows(23))
        self.assertEqual(result["post_g3_samples"], 23)
        self.assertEqual(result["natural_checkpoints"], 1)
        self.assertEqual(result["g4_natural_cycles"],
                         "PENDING_NATURAL_CYCLES")
        self.assertEqual(result["g5_24h"], "PENDING_WINDOW")
        self.assertEqual(result["g4_reasons"], [])

    def test_two_900_second_natural_checkpoints_close_g4_only(self):
        result = self.assess(self.rows(33))
        self.assertEqual(result["natural_checkpoints"], 2)
        self.assertEqual(result["last_checkpoint_interval_seconds"], 900)
        self.assertEqual(result["g4_natural_cycles"], "PASS")
        self.assertEqual(result["g5_24h"], "PENDING_WINDOW")

    def test_historical_checkpoints_never_earn_post_g3_gate(self):
        rows = self.rows(23, pre_g3=15)
        result = self.assess(rows)
        self.assertEqual(result["natural_checkpoints"], 1)
        self.assertEqual(result["post_g3_samples"], 23)
        self.assertEqual(result["g4_natural_cycles"],
                         "PENDING_NATURAL_CYCLES")

    def test_24h_90_natural_checkpoints_complete_g5(self):
        result = self.assess(self.rows(1442))
        self.assertGreaterEqual(result["natural_checkpoints"], 90)
        self.assertGreaterEqual(result["post_g3_observed_span_seconds"], 86400)
        self.assertEqual(result["g4_natural_cycles"], "PASS")
        self.assertEqual(result["g5_24h"], "PASS")
        self.assertEqual(result["http429_unknown_samples"], 0)

    def test_zero_post_samples_are_not_a_success(self):
        result = self.assess([], age=20)
        self.assertEqual(result["g4_natural_cycles"],
                         "PENDING_NATURAL_CYCLES")
        result = self.assess([], age=180)
        self.assertEqual(result["g4_natural_cycles"], "REVIEW")

    def test_collector_gap_is_review(self):
        rows = self.rows(33)
        del rows[8:10]
        result = self.assess(rows)
        self.assertEqual(result["g4_natural_cycles"], "REVIEW")
        self.assertEqual(result["collector_gaps_over_120s"], 1)

    def test_stale_collector_is_review(self):
        result = self.assess(self.rows(33), age=300)
        self.assertEqual(result["g4_natural_cycles"], "REVIEW")
        self.assertIn("STALE_OR_FUTURE_LAST_SAMPLE", result["g4_reasons"])

    def test_invalid_or_partial_source_is_review(self):
        for status in ("PARTIAL", "INVALID"):
            rows = self.rows(33)
            rows[20]["status"] = status
            with self.subTest(status=status):
                self.assertEqual(self.assess(rows)["g4_natural_cycles"],
                                 "REVIEW")

    def test_financial_invariant_failure_is_review(self):
        rows = self.rows(33)
        rows[20]["financial_operations"] = 1
        result = self.assess(rows)
        self.assertEqual(result["g4_natural_cycles"], "REVIEW")
        self.assertEqual(result["financial_invariant"], "FAIL")

    def test_out_of_range_natural_cadence_is_review(self):
        rows = self.rows(33)
        for row in rows[14:29]:
            row["checkpoint_at"] = 1700.0
        result = self.assess(rows)
        self.assertEqual(result["bad_checkpoint_intervals"], 1)
        self.assertEqual(result["g4_natural_cycles"], "REVIEW")

    def test_supervisor_identity_drift_is_review(self):
        rows = self.rows(33)
        rows[20]["runtime"]["pid"] = 9999
        result = self.assess(rows)
        self.assertEqual(result["g4_natural_cycles"], "REVIEW")

    def test_missing_http429_telemetry_blocks_g5_not_g4(self):
        rows = self.rows(1442)
        rows[-1]["http_429_count"] = None
        result = self.assess(rows)
        self.assertEqual(result["g4_natural_cycles"], "PASS")
        self.assertEqual(result["g5_24h"], "REVIEW")
        self.assertEqual(result["http429_unknown_samples"], 1)

    def test_receipt_rejects_wrong_version_and_insecure_permissions(self):
        record = {
            "status": m.RECEIPT_STATUS,
            "candidate_sha": m.CANDIDATE,
            "rollback_bundle_id": "m1-2mLN75Z6aQ",
            "financial_operations": 0,
            "g5_24h_completed": False,
            "production_supervisor_or_watchdog_modified": False,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "g3-result.log"
            path.write_text(json.dumps(record))
            path.chmod(0o600)
            self.assertGreater(m.trusted_cutover_time(path, os.getuid()), 0)
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                m.trusted_cutover_time(path, os.getuid())
            path.chmod(0o600)
            record["status"] = "G3_PLAN_ONLY_NO_HOST_CHANGE"
            path.write_text(json.dumps(record))
            with self.assertRaises(ValueError):
                m.trusted_cutover_time(path, os.getuid())

    def test_samples_path_comes_only_from_isolated_collector_plist(self):
        definition = {
            "Label": m.preflight.LABEL_COLLECTOR,
            "StartInterval": 60,
            "ProgramArguments": [
                "/usr/bin/python3", "-I", "/private/script.py",
                "--state-directory", "/private/state",
                "--runtime", "/private/runtime",
                "--output", "/private/evidence",
                "--expected-commit",
                "93038ca62edff39492f9b8ddb68d890e3e6e5c45",
            ],
        }
        with patch.object(m.preflight, "read_launchagent",
                          return_value=definition):
            self.assertEqual(
                m.existing_samples_path(Path("/tmp/private"), os.getuid()),
                Path("/private/evidence/samples.jsonl"))
            definition["ProgramArguments"].pop(1)
            with self.assertRaises(ValueError):
                m.existing_samples_path(Path("/tmp/private"), os.getuid())

    def test_nonmonotonic_sample_order_is_rejected(self):
        rows = self.rows(33)
        rows[20]["observed_at"] = rows[19]["observed_at"]
        with self.assertRaises(ValueError):
            self.assess(rows)


if __name__ == "__main__":
    unittest.main()
