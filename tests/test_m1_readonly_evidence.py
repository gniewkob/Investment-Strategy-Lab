"""Synthetic-only regression for read-only M1 rolling 24h acceptance."""
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts import m1_readonly_evidence as gate
from scripts import unattended_acceptance as acceptance


def sample(second):
    checkpoint = (second // 900) * 900
    return {
        "observed_at": second,
        "checkpoint_at": checkpoint,
        "status": "OBSERVATION_OK",
        "runtime": {
            "pid": 123, "process_start": "unchanged",
            "clean": True, "commit": acceptance.EXPECTED_SHA,
            "unique_natural_supervisor": True, "publicnode": True,
            "runtime_bound": True, "launchagents_ok": True,
            "launchagent_hashes": ["one", "two"],
        },
        "sources": dict.fromkeys(acceptance.SOURCE_NAMES, "OK"),
        "coverage_ok": True, "watchdog_fresh": True,
        "watchdog_matches": True,
        "backfill": {"available": True},
        "http_429_count": 0,
        "financial_operations": 0,
    }


def full_day():
    return [sample(t) for t in range(0, 86_401, 60)]


class M1RollingAcceptanceTests(unittest.TestCase):
    def test_24h_green_window_needs_natural_checkpoints_and_current_sample(self):
        result = gate.assess(full_day(), 86_410)
        self.assertEqual(result["status"], "PASS")
        self.assertGreaterEqual(result["natural_unique_checkpoints"], 90)
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["http_429_count"], 0)
        self.assertEqual(result["invalid_samples"], 0)

    def test_window_excludes_old_bad_rows_without_erasing_original(self):
        rows = [sample(t) for t in range(-86_400, 86_401, 60)]
        rows[10]["status"] = "INVALID"
        rows[10]["http_429_count"] = None
        rows[10].pop("runtime")
        original = json.dumps(rows, sort_keys=True)
        result = gate.assess(rows, 86_410)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["invalid_samples"], 0)
        self.assertEqual(json.dumps(rows, sort_keys=True), original)

    def test_gaps_partial_unknown_telemetry_and_stale_are_not_passed(self):
        rows = full_day()
        for t in (30_000, 30_060, 30_120):
            rows[t//60]["sources"]["rpc_ethereum"] = "PARTIAL"
            rows[t//60]["status"] = "PARTIAL"
        result = gate.assess(rows, 86_410)
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["ethereum_partial_unique_checkpoints"], 1)
        self.assertEqual(result["partial_samples"], 3)

        rows = full_day()
        rows[20]["http_429_count"] = None
        result = gate.assess(rows, 86_410)
        self.assertIn("HTTP_429_TELEMETRY_NOT_PERSISTED", result["reasons"])

        rows = full_day()
        result = gate.assess(rows, 86_900)
        self.assertIn("M1_LAST_SAMPLE_STALE_OR_FUTURE", result["reasons"])

        rows = full_day()
        rows = [r for r in rows if r["observed_at"] != 30_000
                and r["observed_at"] != 30_060
                and r["observed_at"] != 30_120]
        result = gate.assess(rows, 86_410)
        self.assertIn("COLLECTOR_INTERRUPTION", result["reasons"])

        rows = full_day()
        rows[20]["financial_operations"] = 1
        result = gate.assess(rows, 86_410)
        self.assertIn("M1_FINANCIAL_INVARIANT_FAILED", result["reasons"])

    def test_private_evidence_unchanged_and_public_output_sanitized(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder)
            path = parent / "samples.jsonl"
            rows = full_day()
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            path.chmod(0o600)
            before = path.read_bytes()
            self.assertEqual(gate.read_samples(path), rows)
            self.assertEqual(path.read_bytes(), before)

            path.chmod(0o644)
            with self.assertRaises(ValueError):
                gate.read_samples(path)
            captured = StringIO()
            with redirect_stdout(captured):
                code = gate.main(["--samples", str(path)])
            self.assertEqual(code, 2)
            self.assertEqual(captured.getvalue().strip(),
                             "M1_READONLY_EVIDENCE_REJECTED")
            self.assertNotIn(str(parent), captured.getvalue())
            path.chmod(0o600)

            alias = parent / "alias"
            alias.symlink_to(path)
            with self.assertRaises(OSError):
                gate.read_samples(alias)

    def test_reject_clock_regression_and_short_window(self):
        rows = full_day()
        rows[2]["observed_at"] = rows[1]["observed_at"]
        with self.assertRaises(ValueError):
            gate.assess(rows, 86_410)
        short = gate.assess([sample(t) for t in range(0, 3601, 60)],
                            3601)
        self.assertEqual(short["status"], "PARTIAL")
        self.assertIn("LESS_THAN_24H", short["reasons"])


if __name__ == "__main__":
    unittest.main()
