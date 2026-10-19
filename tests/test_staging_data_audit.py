"""Pure data quality policy tests. No database, secrets or financial execution."""
from contextlib import redirect_stderr
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import staging_data_audit as audit


def snapshot(*, future=0, mismatch=0, pit=1, fixture=0, series=None):
    return {
        "server_time": "2026-10-18T19:00:00+00:00",
        "documents": 3, "versions": 3,
        "pit_eligible": pit,
        "pit_fixture": fixture,
        "pit_nonfixture": pit - fixture if type(pit) is int and type(fixture) is int else 0,
        "future_local_timestamps": future,
        "unmatched_sources": mismatch,
        "series": [] if series is None else series,
    }


def row(code, periods, *, concept="MONTHLY_AVERAGE", interval="1mo"):
    return {"instrument_code": code, "interval_code": interval,
            "value_concept": concept, "periods": periods}


class StagingAuditPolicyTests(unittest.TestCase):
    def test_staging_data_not_ready_with_single_nbp_reference(self):
        data = snapshot(future=1, pit=1, fixture=1, series=[
            row("GOLD_NBP_PLN_G", 1, concept="OTHER_REFERENCE", interval="spot")])
        result = audit.classify_snapshot(data)
        self.assertEqual(result["status"], "MARKET_DATA_NOT_READY")
        self.assertEqual(result["pit_eligible_rows"], 1)
        self.assertEqual(result["pit_fixture_rows"], 1)
        self.assertEqual(result["pit_nonfixture_rows_unreviewed"], 0)
        self.assertFalse(result["publication_vintage_certified"])
        self.assertIn("NO_NONFIXTURE_PIT_EVIDENCE", result["warning_codes"])
        self.assertIn("SYNTHETIC_PIT_FIXTURES_NOT_MARKET_EVIDENCE", result["warning_codes"])
        self.assertEqual(result["future_local_timestamp_rows"], 1)
        self.assertIn("FUTURE_LOCAL_INGESTION_TIMESTAMP", result["warning_codes"])
        self.assertTrue(all(x >= 4 for x in result["monthly_total_return_gaps"].values()))
        self.assertEqual(result["database_writes"], 0)
        self.assertIs(result["data_ready_for_real_trading"], False)
        self.assertIs(result["approval_required_for_schedule"], True)

    def test_late_receipt_does_not_count_toward_screen(self):
        result = audit.classify_snapshot(snapshot(
            pit=0, future=1, series=[]))
        self.assertIn("NO_POINT_IN_TIME_EVIDENCE", result["warning_codes"])
        self.assertIn("INSUFFICIENT_MONTHLY_RESEARCH_HISTORY", result["warning_codes"])

    def test_preliminary_coverage_cannot_self_approve_schedule(self):
        series = [row(code, 4, concept="TOTAL_RETURN_INDEX")
                  for code in audit.MONTHLY_PAPER_REFERENCES]
        series += [row(code, 13) for code in audit.MONTHLY_RESEARCH_WATCH]
        result = audit.classify_snapshot(snapshot(future=0, pit=38, series=series))
        self.assertEqual(result["status"], "COVERAGE_GATE_PASSED_REVIEW_REQUIRED")
        self.assertIsNone(result["data_ready_for_autonomous_experiments"])
        self.assertIs(result["approval_required_for_schedule"], True)
        self.assertEqual(result["warning_codes"], [])
        self.assertFalse(result["data_ready_for_real_trading"])

    def test_fixture_only_full_coverage_does_not_approve_research_readiness(self):
        series = [row(code, 4, concept="TOTAL_RETURN_INDEX")
                  for code in audit.MONTHLY_PAPER_REFERENCES]
        series += [row(code, 13) for code in audit.MONTHLY_RESEARCH_WATCH]
        # Coverage from an upstream read_snapshot is filtered to EXCLUDE
        # all fixture documents. Even a forged full coverage summary cannot
        # override absence of non-fixture PIT evidence.
        result = audit.classify_snapshot(snapshot(
            pit=38, fixture=38, series=series))
        self.assertEqual(result["pit_nonfixture_rows_unreviewed"], 0)
        self.assertIn("NO_NONFIXTURE_PIT_EVIDENCE", result["warning_codes"])
        self.assertEqual(result["status"], "MARKET_DATA_NOT_READY")
        self.assertFalse(result["data_ready_for_autonomous_experiments"])
        self.assertFalse(result["data_ready_for_real_trading"])

    def test_fixture_count_must_match_total_pit_coverage(self):
        bad = snapshot(pit=1, fixture=1)
        bad["pit_nonfixture"] = 1
        with self.assertRaisesRegex(ValueError, "must sum"):
            audit.classify_snapshot(bad)
        bad = snapshot(pit=1, fixture=1)
        bad.pop("pit_fixture")
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            audit.classify_snapshot(bad)
        with self.assertRaises(ValueError):
            audit.classify_snapshot(snapshot(pit=1, fixture=2))

    def test_price_only_monthly_index_cannot_fake_total_return(self):
        data = snapshot(series=[row("EQUITY_TR_PLN", 100, concept="OTHER_REFERENCE")])
        result = audit.classify_snapshot(data)
        self.assertEqual(result["monthly_total_return_gaps"]["EQUITY_TR_PLN"],4)

    def test_daily_prices_do_not_count_as_monthly_history(self):
        data = snapshot(series=[row("BRENT_EIA_USD_BBL", 900, interval="1d")])
        result = audit.classify_snapshot(data)
        self.assertEqual(result["monthly_research_watch_gaps"]["BRENT_EIA_USD_BBL"],13)

    def test_partial_coverage_reports_exact_gaps(self):
        data = snapshot(series=[row("BRENT_EIA_USD_BBL", 9),
                                row("COPPER_WB_USD_T", 5),
                                row("GOLD_TR_PLN", 3, concept="TOTAL_RETURN_INDEX")])
        result = audit.classify_snapshot(data)
        self.assertEqual(result["monthly_research_watch_gaps"]["BRENT_EIA_USD_BBL"],4)
        self.assertEqual(result["monthly_research_watch_gaps"]["COPPER_WB_USD_T"],8)
        self.assertEqual(result["monthly_total_return_gaps"]["GOLD_TR_PLN"],1)

    def test_source_mismatch_blocks_data_gate(self):
        data = snapshot(mismatch=2, series=[])
        result = audit.classify_snapshot(data)
        self.assertIn("DOCUMENT_SOURCE_MISMATCH", result["warning_codes"])

    def test_wrong_counts_fail_closed(self):
        with self.assertRaises(ValueError):
            audit.classify_snapshot(snapshot(pit=-1))
        with self.assertRaises(ValueError):
            audit.classify_snapshot(snapshot(pit="1"))

    def test_invalid_series_fail_closed(self):
        with self.assertRaises(ValueError):
            audit.classify_snapshot(snapshot(series=[row("BRENT_EIA_USD_BBL", -2)]))
        with self.assertRaises(ValueError):
            audit.classify_snapshot(snapshot(series="not_a_list"))

    def test_markdown_is_explicit_about_insufficient_data(self):
        result = audit.classify_snapshot(snapshot(future=1))
        text = audit.make_markdown(result)
        self.assertIn("MARKET_DATA_NOT_READY", text)
        self.assertIn("FUTURE_LOCAL_INGESTION_TIMESTAMP", text)
        self.assertIn("No real orders", text)
        self.assertNotIn("postgresql://", text)

    def test_main_generates_audit_artifact_without_secrets(self):
        raw = snapshot(future=1)
        with tempfile.TemporaryDirectory() as tmp:
            env = {"NEON_DATABASE_URL":"sensitive-test-only",
                   "ISL_DATA_AUDIT_DIR": tmp}
            with patch.dict("os.environ", env, clear=True):
                with patch.object(audit, "read_snapshot", return_value=raw):
                    self.assertEqual(audit.main(),0)
            a = json.loads((Path(tmp)/"audit.json").read_text())
            m = (Path(tmp)/"audit.md").read_text()
            self.assertEqual(a["status"], "MARKET_DATA_NOT_READY")
            self.assertEqual(a["database_writes"],0)
            self.assertNotIn("sensitive-test-only",m)
            self.assertNotIn("sensitive-test-only",(Path(tmp)/"audit.json").read_text())

    def test_main_suppresses_db_exception_details(self):
        with patch.dict("os.environ",{"NEON_DATABASE_URL":"sensitive-test-only"}):
            with patch.object(audit, "read_snapshot",
                              side_effect=RuntimeError("private-connection-string")):
                log = StringIO()
                with redirect_stderr(log):
                    self.assertEqual(audit.main(), 2)
        self.assertEqual(log.getvalue().strip(),
                         "STAGING_DATA_AUDIT_FAILED: RuntimeError")
        self.assertNotIn("private-connection-string", log.getvalue())


if __name__ == "__main__":
    unittest.main()
