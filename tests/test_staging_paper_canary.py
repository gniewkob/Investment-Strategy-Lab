"""Synthetic-only offline tests for the fixed, manually invoked journal canary."""
from __future__ import annotations

from contextlib import redirect_stderr
from datetime import timedelta
from decimal import Decimal
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.staging_preflight import EXPECTED_HOST
from scripts import staging_paper_canary as canary


GOOD = (f"postgresql://isl_agent_staging_limited:synthetic-test-only@{EXPECTED_HOST}"
        "/investment_lab?sslmode=verify-full")


class FakeConnection:
    """Tiny fake implementing only the known append-only SQL sequence."""
    def __init__(self, state):
        self.state = state
        self.fetchone_value = None
        self.fetchall_value = []
        self.commands = []
        self.committed = False

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self
    def commit(self): self.committed = True

    def execute(self, sql, params=None):
        self.commands.append(sql)
        self.fetchone_value, self.fetchall_value = None, []
        compact = " ".join(sql.split())
        if "SELECT current_user,current_database()" in compact:
            self.fetchone_value = ("isl_agent_staging_limited", "investment_lab", True, False)
        elif "SELECT model_code FROM investment_lab.models" in compact:
            self.fetchall_value = [(x,) for x in canary.MODELS]
        elif "FROM investment_lab.prices_asof(" in compact:
            self.fetchall_value = self.state["evidence"]
        elif "INSERT INTO investment_lab.agent_cycles" in compact:
            if "cycle" not in self.state:
                self.state["cycle"] = (params[2], params[3], params[4], 0, 0, params[1])
                self.fetchone_value = (params[0],)
        elif "INSERT INTO investment_lab.agent_paper_decisions" in compact:
            model = params[1]
            self.state.setdefault("decisions", {})[model] = (
                model, "HOLD_CASH", True, {}, json.loads(params[3]), params[4])
        elif "FROM investment_lab.agent_cycles WHERE run_key=" in compact:
            self.fetchone_value = self.state.get("cycle")
        elif "FROM investment_lab.agent_paper_decisions WHERE run_key=" in compact:
            self.fetchall_value = sorted(self.state.get("decisions", {}).values())
        else:
            raise AssertionError(f"Unexpected SQL: {compact[:100]}")

    def fetchone(self): return self.fetchone_value
    def fetchall(self): return self.fetchall_value


class JournalCanaryTests(unittest.TestCase):
    def setUp(self):
        self.state = {"evidence": []}
        self.connections = []

    def connect(self, *args, **kwargs):
        self.assertEqual(kwargs["sslmode"], "verify-full")
        self.assertEqual(kwargs["sslrootcert"], "/etc/ssl/certs/ca-certificates.crt")
        self.assertIs(kwargs["autocommit"], False)
        db = FakeConnection(self.state)
        self.connections.append(db)
        return db

    def test_one_cycle_then_replay_produces_no_duplicates(self):
        with patch("psycopg.connect", side_effect=self.connect):
            first = canary.run_once(GOOD)
            second = canary.run_once(GOOD)
        self.assertTrue(first["newly_written"])
        self.assertFalse(second["newly_written"])
        self.assertEqual(first["input_sha256"], second["input_sha256"])
        self.assertEqual(set(self.state["decisions"]), set(canary.MODELS))
        self.assertEqual(second["paper_decisions"], 3)
        self.assertEqual(second["paper_fills"], 0)
        self.assertEqual(second["real_orders"], 0)
        self.assertTrue(all(db.committed for db in self.connections))
        self.assertFalse(any(" UPDATE " in " ".join(q.split()).upper()
                             or " DELETE " in " ".join(q.split()).upper()
                             for db in self.connections for q in db.commands))

    def test_conflicting_journal_fingerprint_fails_without_update(self):
        with patch("psycopg.connect", side_effect=self.connect):
            canary.run_once(GOOD)
            old = self.state["cycle"]
            self.state["cycle"] = ("f" * 64, *old[1:])
            with self.assertRaisesRegex(RuntimeError, "differs"):
                canary.run_once(GOOD)
        self.assertEqual(len(self.state["decisions"]), 3)

    def test_future_observation_rejected_before_insert(self):
        self.state["evidence"] = [(
            "BRENT_EIA_USD_BBL", "eia_brent_daily", canary.AS_OF,
            "1d", Decimal("99"), "DAILY_SPOT", 1,
            canary.AS_OF + timedelta(seconds=1),
            "00000000-0000-0000-0000-000000000001")]
        with patch("psycopg.connect", side_effect=self.connect):
            with self.assertRaisesRegex(RuntimeError, "future-dated"):
                canary.run_once(GOOD)
        self.assertNotIn("cycle", self.state)

    def test_fingerprint_includes_revisions_and_provenance(self):
        base = [{"instrument_code": "BRENT", "source_code": "eia",
                 "observed_for": "2026-10-17T00:00:00+00:00",
                 "interval_code": "1d", "price_value": "100",
                 "value_concept": "DAILY_SPOT", "revision_no": 1,
                 "available_at": "2026-10-18T00:00:00+00:00",
                 "document_id": "source-v1"}]
        a = canary.fixed_fingerprint(base)
        self.assertEqual(a, canary.fixed_fingerprint(base))
        b = [dict(base[0], revision_no=2, document_id="source-v2")]
        self.assertNotEqual(a, canary.fixed_fingerprint(b))
        self.assertEqual(len(a), 64)

    def test_main_creates_report_and_verifies_retry(self):
        sample = {"status": "STAGING_PAPER_CANARY_VERIFIED",
                  "run_key": canary.RUN_KEY, "as_of": canary.AS_OF.isoformat(),
                  "input_sha256": "a" * 64, "records_seen": 1,
                  "paper_decisions": 3, "all_hold_cash": True,
                  "paper_fills": 0, "real_orders": 0,
                  "newly_written": True, "test_type": "SYNTHETIC_ONLY"}
        replay = dict(sample, newly_written=False)
        with tempfile.TemporaryDirectory() as td:
            with patch.dict("os.environ", {"NEON_DATABASE_URL": GOOD}):
                with patch.object(canary, "check_connection") as preflight:
                    with patch.object(canary, "run_once", side_effect=[sample, replay]):
                        with patch("sys.argv", ["canary", "--out-dir", td]):
                            self.assertEqual(canary.main(), 0)
            preflight.assert_called_once_with(GOOD)
            outcome = json.loads((Path(td) / "cycle.json").read_text())
            report = (Path(td) / "report.md").read_text()
            self.assertEqual(outcome["retry_inserted_new_rows"], 0)
            self.assertEqual(outcome["real_orders"], 0)
            self.assertIn("SYNTHETIC HOLD_CASH", report)

    def test_error_does_not_print_sensitive_text(self):
        with patch.dict("os.environ", {"NEON_DATABASE_URL": GOOD}):
            with patch.object(canary, "check_connection",
                              side_effect=RuntimeError("do-not-print-secret")):
                with patch("sys.argv", ["canary"]):
                    stderr = StringIO()
                    with redirect_stderr(stderr):
                        self.assertEqual(canary.main(), 2)
        self.assertNotIn("do-not-print-secret", stderr.getvalue())
        self.assertNotIn("synthetic-test-only", stderr.getvalue())
        self.assertEqual(stderr.getvalue().strip(),
                         "STAGING_PAPER_CANARY_FAILED: RuntimeError")


if __name__ == "__main__":
    unittest.main()
