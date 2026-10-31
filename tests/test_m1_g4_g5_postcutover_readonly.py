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
                "coverage_ok": True,
                "watchdog_fresh": True,
                "watchdog_matches": True,
                "backfill": {"available": True},
                "sources": {name: "OK" for name in m.acceptance.SOURCE_NAMES},
                "runtime": {
                    "unique_natural_supervisor": True,
                    "pid": 1324,
                    "process_start": "constant-start",
                    "launchagent_hashes": ["supervisor-sha", "watchdog-sha"],
                    "clean": True,
                    "launchagents_ok": True,
                    "publicnode": True,
                    "runtime_bound": True,
                    "commit": m.acceptance.EXPECTED_SHA,
                    "expected_commit": m.acceptance.EXPECTED_SHA,
                },
            })
        return rows

    def assess(self, rows, *, age=20):
        now = (rows[-1]["observed_at"] + age
               if rows else self.CUTOVER + age)
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


    def test_real_health_predicate_is_not_mocked(self):
        rows = self.rows(33)
        self.assertTrue(m.safe_healthy(rows[0]))
        for mutate in (
            lambda r: r["sources"].update({"rpc_ethereum": "PARTIAL"}),
            lambda r: r.update({"coverage_ok": False}),
            lambda r: r.update({"watchdog_fresh": False}),
            lambda r: r.update({"watchdog_matches": False}),
            lambda r: r["backfill"].update({"available": False}),
            lambda r: r["runtime"].update({"runtime_bound": False}),
            lambda r: r["runtime"].update({"commit": "0" * 40}),
        ):
            case = self.rows(33)
            mutate(case[20])
            self.assertEqual(case[20]["status"], "OBSERVATION_OK")
            self.assertFalse(m.safe_healthy(case[20]))
            self.assertEqual(self.assess(case)["g4_natural_cycles"],
                             "REVIEW")

    def test_missing_natural_checkpoint_at_end_rejected_even_when_24h_full(self):
        # Collector keeps delivering healthy observations although the
        # supervisor stops producing checkpoints near the window end.
        rows = self.rows(1442)
        newest = self.CUTOVER + 93 * 900
        for r in rows:
            if r["checkpoint_at"] > newest:
                r["checkpoint_at"] = newest
        report = self.assess(rows)
        self.assertGreaterEqual(report["natural_checkpoints"], 90)
        self.assertGreaterEqual(report["post_g3_observed_span_seconds"], 86400)
        self.assertEqual(report["bad_checkpoint_intervals"], 0)
        self.assertEqual(report["unhealthy_samples"], 0)
        self.assertIn("CHECKPOINT_END_BOUNDARY_UNCOVERED", report["g4_reasons"])
        self.assertEqual(report["g4_natural_cycles"], "REVIEW")
        self.assertEqual(report["g5_24h"], "REVIEW")

    def test_first_natural_checkpoint_must_cover_start_boundary(self):
        rows = self.rows(33)
        first = self.CUTOVER + 900
        for r in rows:
            if r["checkpoint_at"] == first:
                r["checkpoint_at"] = self.CUTOVER - 300
        result = self.assess(rows)
        self.assertEqual(result["natural_checkpoints"], 1)
        self.assertIn("CHECKPOINT_START_BOUNDARY_UNCOVERED",
                      result["g4_reasons"])
        self.assertEqual(result["g4_natural_cycles"], "REVIEW")

    def test_no_natural_checkpoint_after_1020_seconds_is_review(self):
        result = self.assess(self.rows(19))
        self.assertEqual(result["natural_checkpoints"], 1)
        # One natural checkpoint at 900s is still within endpoint coverage.
        self.assertEqual(result["g4_natural_cycles"],
                         "PENDING_NATURAL_CYCLES")
        rows = self.rows(33)
        for r in rows:
            r["checkpoint_at"] = self.CUTOVER - 300
        result = self.assess(rows)
        self.assertEqual(result["natural_checkpoints"], 0)
        self.assertIn("NO_NATURAL_CHECKPOINT_AFTER_START",
                      result["g4_reasons"])
        self.assertEqual(result["g4_natural_cycles"], "REVIEW")

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
