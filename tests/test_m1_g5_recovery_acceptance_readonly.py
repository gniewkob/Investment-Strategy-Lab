"""Strict offline regression of a fixed G5 recovery window (no host access)."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import m1_g5_recovery_acceptance_readonly as m


class G5RecoveryReadOnlyTests(unittest.TestCase):
    @staticmethod
    def row(at, checkpoint):
        return {
            "observed_at": at,
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
                "process_start": "fixed-natural-supervisor-start",
                "launchagent_hashes": ["supervisor-hash", "watchdog-hash"],
                "clean": True,
                "launchagents_ok": True,
                "publicnode": True,
                "runtime_bound": True,
                "commit": m.acceptance.EXPECTED_SHA,
                "expected_commit": m.acceptance.EXPECTED_SHA,
            },
        }

    def rows(self, n):
        start = m.RECOVERY_START
        return [
            self.row(
                start + 60 * (i + 1),
                start + 900 * ((i + 1) // 15) if i >= 14
                else start - 300,
            )
            for i in range(n)
        ]

    def assess(self, rows, *, offset=13, g3_ago=3600):
        now = rows[-1]["observed_at"] + offset if rows else m.RECOVERY_START + offset
        return m.assess(rows, m.RECOVERY_START - g3_ago, now)

    def test_recovery_start_immutable_and_utc(self):
        self.assertEqual(m.RECOVERY_START_ISO, "2026-11-01T18:18:51Z")
        self.assertEqual(m.utc(m.RECOVERY_START), m.RECOVERY_START_ISO.replace("Z", "+00:00").replace("+00:00", "Z"))

    def test_clean_24h_90_checkpoint_recovery_pass(self):
        report = self.assess(self.rows(1442))
        self.assertEqual(report["recovery_window"]["g5_status"], "PASS")
        self.assertGreaterEqual(report["recovery_window"]["natural_checkpoints"], 90)
        self.assertGreaterEqual(report["recovery_window"]["span_seconds"], 86400)
        self.assertEqual(report["g6"], "BLOCKED_PENDING_FINAL_SIGNOFF")
        self.assertEqual(report["financial_operations_performed_by_assessor"], 0)

    def test_bad_original_window_never_becomes_clean_retroactively(self):
        first = self.row(m.RECOVERY_START - 60, m.RECOVERY_START - 900)
        first["status"] = "PARTIAL"
        first["coverage_ok"] = False
        first["sources"]["rpc_ethereum"] = "PARTIAL"
        rows = [first] + self.rows(1442)
        output = self.assess(rows)
        self.assertEqual(output["historical_g3_based_acceptance"]["g5_status"],
                         "REVIEW")
        self.assertTrue(output["historical_g3_based_acceptance"]
                        ["preserved_not_reclassified"])
        self.assertEqual(output["recovery_window"]["g5_status"], "PASS")
        self.assertEqual(output["prior_incidents"]["partial_unique_checkpoint_groups"], 1)
        self.assertEqual(output["prior_incidents"]["source_failure_counts"]
                         ["rpc_ethereum:PARTIAL"], 1)

    def test_before_first_24h_is_pending(self):
        report = self.assess(self.rows(40))
        self.assertEqual(report["recovery_window"]["g4_status"], "PASS")
        self.assertEqual(report["recovery_window"]["g5_status"], "PENDING_WINDOW")

    def test_historical_checkpoints_do_not_count_for_recovery(self):
        first = self.row(m.RECOVERY_START - 60, m.RECOVERY_START - 900)
        report = self.assess([first] + self.rows(22))
        self.assertEqual(report["recovery_window"]["natural_checkpoints"], 1)
        self.assertEqual(report["recovery_window"]["g5_status"], "PENDING_WINDOW")

    def test_partial_inside_recovery_is_review_even_at_24h(self):
        rows = self.rows(1442)
        rows[500]["status"] = "PARTIAL"
        rows[500]["sources"]["rpc_ethereum"] = "PARTIAL"
        rows[500]["coverage_ok"] = False
        report = self.assess(rows)
        self.assertEqual(report["recovery_window"]["g5_status"], "REVIEW")
        self.assertIn("UNHEALTHY_SAMPLES", report["recovery_window"]["reasons"])

    def test_122_second_gap_blocks_recovery(self):
        rows = self.rows(1442)
        del rows[100:102]
        report = self.assess(rows)
        self.assertEqual(report["recovery_window"]["collector_gaps_over_120s"], 1)
        self.assertEqual(report["recovery_window"]["g5_status"], "REVIEW")

    def test_watchdog_and_history_coverage_fail_closed(self):
        for name, mutation in (
            ("watchdog", lambda r: r.update({"watchdog_matches": False})),
            ("history", lambda r: r.update({"coverage_ok": False})),
            ("identity", lambda r: r["runtime"].update({"pid": 2})),
            ("rpc", lambda r: r["sources"].update({"rpc_base": "UNAVAILABLE"})),
            ("http429_missing", lambda r: r.update({"http_429_count": None})),
            ("financial", lambda r: r.update({"financial_operations": 1})),
        ):
            with self.subTest(name=name):
                rows = self.rows(1442)
                mutation(rows[100])
                self.assertEqual(self.assess(rows)["recovery_window"]["g5_status"],
                                 "REVIEW")

    def test_no_advance_of_original_receipt_boundary(self):
        with self.assertRaises(ValueError):
            m.assess(self.rows(20), m.RECOVERY_START, m.RECOVERY_START + 300)
        with self.assertRaises(ValueError):
            m.assess(self.rows(20), m.RECOVERY_START + 1,
                     m.RECOVERY_START + 300)

    def test_recent_last_sample_must_be_fresh(self):
        report = self.assess(self.rows(1442), offset=121)
        self.assertEqual(report["recovery_window"]["g5_status"], "REVIEW")
        self.assertIn("STALE_OR_FUTURE_LAST_SAMPLE",
                      report["recovery_window"]["reasons"])

    def test_fixed_window_rejects_end_checkpoint_starvation(self):
        rows = self.rows(1442)
        checkpoint_end = m.RECOVERY_START + 90 * 900
        for row in rows:
            if row["checkpoint_at"] > checkpoint_end:
                row["checkpoint_at"] = checkpoint_end
        report = self.assess(rows)
        self.assertEqual(report["recovery_window"]["g5_status"], "REVIEW")
        self.assertIn("CHECKPOINT_END_BOUNDARY_UNCOVERED",
                      report["recovery_window"]["reasons"])

    def test_8_partial_checkpoint_groups_and_no_private_fields(self):
        rows = []
        for i in range(8):
            cp = m.RECOVERY_START - 4200 + i * 450
            for j in range(3):
                row = self.row(cp + 50 + j * 60, cp)
                row["status"] = "PARTIAL"
                row["coverage_ok"] = False
                row["private_credential"] = "SECRET_SHOULD_NEVER_APPEAR"
                row["sources"]["rpc_ethereum"] = "PARTIAL"
                rows.append(row)
        # All rows need to predate pinned recovery boundary.
        self.assertLess(rows[-1]["observed_at"], m.RECOVERY_START)
        result = m.incident_analysis(rows, m.RECOVERY_START - 5000)
        self.assertEqual(result["partial_unique_checkpoint_groups"], 8)
        self.assertEqual(len(result["partial_checkpoint_groups"]), 8)
        self.assertEqual(result["source_failure_counts"]
                         ["rpc_ethereum:PARTIAL"], 24)
        self.assertNotIn("SECRET_SHOULD_NEVER_APPEAR", json.dumps(result))

    def test_recovery_recurrence_groups_distinct_natural_checkpoints(self):
        rows = self.rows(1442)
        for n, index in enumerate((100, 300, 500, 700, 900)):
            for row in rows[index:index + 3]:
                row["status"] = "PARTIAL"
                row["coverage_ok"] = False
                row["private_credential"] = "RECOVERY_PRIVATE_TOKEN"
                row["sources"]["rpc_ethereum" if n % 2 == 0
                               else "rpc_base"] = (
                    "PARTIAL" if n % 2 == 0 else "UNAVAILABLE")
        report = self.assess(rows)
        incident = report["recovery_incidents"]
        self.assertEqual(incident["partial_unique_checkpoint_groups"], 5)
        self.assertEqual(incident["status_counts"]["PARTIAL"], 15)
        self.assertEqual(incident["unhealthy_samples"], 15)
        self.assertEqual(incident["source_failure_counts"]
                         ["rpc_ethereum:PARTIAL"], 9)
        self.assertEqual(incident["source_failure_counts"]
                         ["rpc_base:UNAVAILABLE"], 6)
        self.assertIsNotNone(incident["last_partial_utc"])
        self.assertEqual(incident["last_partial_utc"],
                         m.utc(rows[902]["observed_at"]))
        self.assertNotIn("RECOVERY_PRIVATE_TOKEN", json.dumps(report))
        self.assertEqual(report["recovery_window"]["g5_status"], "REVIEW")

    def test_original_incidents_not_confused_with_recovery_incidents(self):
        historic = self.row(m.RECOVERY_START - 60,
                            m.RECOVERY_START - 900)
        historic["status"] = "PARTIAL"
        historic["sources"]["rpc_ethereum"] = "PARTIAL"
        rows = [historic] + self.rows(1442)
        rows[100]["status"] = "PARTIAL"
        rows[100]["sources"]["rpc_base"] = "UNAVAILABLE"
        result = self.assess(rows)
        self.assertEqual(result["prior_incidents"]
                         ["source_failure_counts"]["rpc_ethereum:PARTIAL"], 1)
        self.assertEqual(result["recovery_incidents"]
                         ["source_failure_counts"]["rpc_base:UNAVAILABLE"], 1)
        self.assertNotIn("rpc_ethereum:PARTIAL",
                         result["recovery_incidents"]["source_failure_counts"])
        self.assertEqual(result["historical_g3_based_acceptance"]["g5_status"],
                         "REVIEW")

    def test_recovery_window_incident_gap_detected_separately(self):
        rows = self.rows(1442)
        del rows[120:122]
        output = self.assess(rows)
        self.assertEqual(output["recovery_incidents"]["poll_gaps_over_120s"], 1)
        self.assertEqual(output["recovery_window"]["collector_gaps_over_120s"], 1)
        self.assertEqual(output["recovery_window"]["g5_status"], "REVIEW")

    def test_clean_recovery_has_empty_recurrence_diagnostics(self):
        result = self.assess(self.rows(1442))
        incident = result["recovery_incidents"]
        self.assertEqual(incident["partial_unique_checkpoint_groups"], 0)
        self.assertEqual(incident["unhealthy_samples"], 0)
        self.assertEqual(incident["poll_gaps_over_120s"], 0)
        self.assertIsNone(incident["last_partial_utc"])
        self.assertIsNone(incident["last_unhealthy_utc"])
        self.assertEqual(result["recovery_window"]["g5_status"], "PASS")

    def test_gap_is_preserved_in_historical_incident_summary(self):
        a = self.row(m.RECOVERY_START - 190, m.RECOVERY_START - 900)
        b = self.row(m.RECOVERY_START - 67.6, m.RECOVERY_START - 900)
        result = m.incident_analysis([a, b], m.RECOVERY_START - 500)
        self.assertEqual(result["poll_gaps_over_120s"], 1)
        self.assertAlmostEqual(result["poll_gap_examples"][0]["seconds"], 122.4)

    def test_original_and_recovery_results_are_separate(self):
        rows = self.rows(1442)
        output = self.assess(rows)
        self.assertIn("historical_g3_based_acceptance", output)
        self.assertIn("recovery_window", output)
        self.assertIn("prior_incidents", output)
        self.assertNotIn("g5_24h_completed", output)
        self.assertFalse(output["historical_ledger_modified"])

    def test_cli_injects_existing_evidence_only_and_returns_pending(self):
        with patch.object(m.original, "trusted_cutover_time",
                          return_value=m.RECOVERY_START - 3600), \
             patch.object(m.original, "existing_samples_path",
                          return_value=Path("/synthetic/samples.jsonl")), \
             patch.object(m.evidence, "read_samples", return_value=self.rows(20)), \
             patch.object(m.time, "time", return_value=m.RECOVERY_START + 1200), \
             patch.object(m.original.os, "getuid", return_value=501), \
             patch("builtins.print") as printed:
            self.assertEqual(m.main(["--g3-receipt", "/synthetic/g3.log"]), 0)
            self.assertIn("PENDING_WINDOW", printed.call_args.args[0])

    def test_cli_rejects_invalid_receipt_without_printing_path(self):
        with patch.object(m.original, "trusted_cutover_time",
                          side_effect=ValueError("/private/my-secret")):
            with patch("builtins.print") as printed:
                self.assertEqual(m.main(["--g3-receipt", "/private/my-secret"]), 2)
                self.assertEqual(printed.call_args.args[0],
                                 "M1_G5_RECOVERY_READONLY_REJECTED")


if __name__ == "__main__":
    unittest.main()
