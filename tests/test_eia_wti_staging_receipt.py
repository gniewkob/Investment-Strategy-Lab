"""Synthetic offline safety/coverage tests for manual WTI/Neon/EIA receipt.

No network, no real Neon connection, no secrets, no source prices exported.
"""
from __future__ import annotations

from contextlib import redirect_stderr
from datetime import date, datetime, timezone
from decimal import Decimal
from io import StringIO
import json
from unittest import TestCase
from unittest.mock import patch

from scripts import eia_wti_staging_receipt as combined
from scripts.eia_readonly_audit import read_local_reference_with_digest
from src.isl_v2.eia_sources import Snapshot, Spot, SOURCES


def snapshot(records=None, *, source="UNVERIFIED_HISTORICAL_PUBLICATION"):
    if records is None:
        records = [
            {"instrument_code": combined.INSTRUMENT, "interval_code": "1d",
             "return_basis": "PRICE_ONLY",
             "observed_for": "2024-01-02T00:00:00+00:00",
             "close_price": "70.12"},
            {"instrument_code": combined.INSTRUMENT, "interval_code": "1d",
             "return_basis": "PRICE_ONLY",
             "observed_for": "2026-08-25T00:00:00+00:00",
             "close_price": "71.23"},
            {"instrument_code": "BRENT_EIA_USD_BBL", "interval_code": "1d",
             "return_basis": "PRICE_ONLY",
             "observed_for": "2026-08-25T00:00:00+00:00",
             "close_price": "80.99"},
        ]
    return {"mode": "RETROSPECTIVE_RESEARCH_ONLY",
            "source_vintage": source, "records": records}


def manifest():
    return {"series_counts": {combined.INSTRUMENT: 2},
            "database_writes": 0,
            "source_vintage": "UNVERIFIED_HISTORICAL_PUBLICATION"}


def official():
    return Snapshot(
        SOURCES["wti"][0], SOURCES["wti"][1], SOURCES["wti"][2],
        "a" * 64, date(2026, 10, 15),
        datetime(2026, 10, 19, 18, 0, tzinfo=timezone.utc),
        (
            Spot(date(2024, 1, 2), Decimal("70.12")),
            Spot(date(2026, 8, 25), Decimal("71.23")),
            Spot(date(2026, 10, 14), Decimal("72.34")),
        ), 3,
    )


class StagingEiaReceiptTests(TestCase):
    def test_public_reference_is_canonical_and_exactly_parsed(self):
        data = combined.staging_reference_csv(snapshot(), expected_rows=2)
        self.assertEqual(data.count(b"\n"), 3)
        self.assertTrue(data.startswith(
            b"instrument_code,observed_for,close_price\n"))
        self.assertLess(data.index(b"2024-01-02"), data.index(b"2026-08-25"))
        self.assertNotIn(b"BRENT_EIA_USD_BBL", data)
        self.assertNotIn(b"postgresql://", data)

    def test_fails_closed_on_drifting_stored_window_and_duplicate_day(self):
        with self.assertRaisesRegex(ValueError, "coverage drifted"):
            combined.staging_reference_csv(snapshot(), expected_rows=3)
        bad = snapshot()["records"]
        bad.append(dict(bad[0]))
        with self.assertRaisesRegex(ValueError, "window or price"):
            combined.staging_reference_csv(snapshot(bad), expected_rows=3)
        bad = snapshot()["records"]
        bad[0] = {**bad[0], "observed_for": "2026-08-26T00:00:00+00:00"}
        with self.assertRaisesRegex(ValueError, "window or price"):
            combined.staging_reference_csv(snapshot(bad), expected_rows=2)

    def test_refuses_fake_verified_vintage_or_wrong_reference_basis(self):
        with self.assertRaisesRegex(ValueError, "snapshot contract"):
            combined.staging_reference_csv(
                snapshot(source="VERIFIED_HISTORICAL_PUBLICATION"), expected_rows=2)
        bad = snapshot()["records"]
        bad[0] = {**bad[0], "return_basis": "TOTAL_RETURN_INDEX"}
        with self.assertRaisesRegex(ValueError, "reference type"):
            combined.staging_reference_csv(snapshot(bad), expected_rows=2)

    def test_one_read_only_staging_and_source_receipt_no_prices(self):
        with (patch.object(combined, "EXPECTED_STORED_ROWS", 2),
              patch.object(combined, "EXPECTED_MISSING", 1),
              patch.object(combined, "fetch_staging_history",
                           return_value=(snapshot(), manifest())) as staging,
              patch.object(combined, "fetch_official",
                           return_value=official()) as eia):
            report = combined.audit("safe-dsn-not-printed")
        staging.assert_called_once_with("safe-dsn-not-printed")
        eia.assert_called_once()
        self.assertEqual(eia.call_args.args[0], "wti")
        self.assertEqual(eia.call_args.kwargs["max_age_days"], 1100)
        self.assertEqual(report["status"], "WTI_EIA_GAP_REVIEW_PASSED_READ_ONLY")
        self.assertEqual(report["staging_reference_rows"], 2)
        self.assertEqual(report["missing_source_dates_after_cutoff"], 1)
        self.assertEqual(report["database_connections"], 1)
        self.assertEqual(report["database_reads"], 1)
        self.assertEqual(report["database_writes"], 0)
        self.assertTrue(report["historical_reader_acl_verified"])
        self.assertFalse(report["reference_csv_source_provenance_verified"])
        self.assertFalse(report["independent_point_in_time_market_data_certified"])
        self.assertFalse(report["schedule_enabled"])
        self.assertNotIn("operator_supplied_local_reference_csv_sha256", report)
        printed = json.dumps(report)
        for restricted in ("70.12", "71.23", "72.34",
                           "80.99", "safe-dsn-not-printed"):
            self.assertNotIn(restricted, printed)

    def test_missing_before_cutoff_or_wrong_source_fails_review(self):
        altered = official()
        altered = Snapshot(
            altered.instrument_code, altered.source_code,
            altered.url, altered.sha256_hex,
            altered.release_day, altered.downloaded_at,
            (Spot(date(2024, 1, 2), Decimal("70.13")),)
            + altered.observations[1:], altered.raw_count)
        with (patch.object(combined, "EXPECTED_STORED_ROWS", 2),
              patch.object(combined, "EXPECTED_MISSING", 1),
              patch.object(combined, "fetch_staging_history",
                           return_value=(snapshot(), manifest())),
              patch.object(combined, "fetch_official", return_value=altered)):
            with self.assertRaisesRegex(ValueError, "integrity"):
                combined.audit("safe-dsn")

    def test_refuses_source_fetch_if_staging_snapshot_invalid(self):
        with (patch.object(combined, "fetch_staging_history",
                           return_value=(snapshot(), manifest())),
              patch.object(combined, "fetch_official") as fetch):
            with self.assertRaisesRegex(ValueError, "coverage drifted"):
                combined.audit("safe-dsn")
            fetch.assert_not_called()

    def test_failure_message_scrubs_credentials(self):
        stderr = StringIO()
        with (patch.object(combined, "audit",
                           side_effect=ValueError("postgresql://secret:password@host")),
              redirect_stderr(stderr)):
            status = combined.main()
        self.assertEqual(status, 2)
        self.assertEqual(stderr.getvalue(),
                         "WTI_STAGING_RECEIPT_FAILED: ValueError\n")


if __name__ == "__main__":
    import unittest
    unittest.main()
