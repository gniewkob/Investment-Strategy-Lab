"""Offline, synthetic regressions for frozen WTI coverage review (no Neon)."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

from scripts import eia_wti_gap_receipt as wti
from src.isl_v2.eia_sources import SOURCES, Snapshot, Spot

FIRST = date(2026, 10, 12)
LAST = date(2026, 10, 14)
CUTOFF = date(2026, 10, 13)
RELEASE = date(2026, 10, 15)
FETCHED = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)


def official():
    return Snapshot(
        SOURCES["wti"][0], SOURCES["wti"][1], SOURCES["wti"][2],
        "a" * 64, RELEASE, FETCHED,
        (Spot(FIRST, Decimal("91.10")),
         Spot(CUTOFF, Decimal("92.11")),
         Spot(LAST, Decimal("93.12"))), 3)


def reference():
    return {FIRST: Decimal("91.10"), CUTOFF: Decimal("92.11")}


def review(s=None, ref=None, **updates):
    params = dict(
        window_first=FIRST, window_last=LAST,
        reference_cutoff=CUTOFF, expected_release=RELEASE,
        expected_missing=1, reference_sha256="b" * 64)
    params.update(updates)
    return wti.review_gap(official() if s is None else s,
                          reference() if ref is None else ref, **params)


class FrozenWtiReceiptTests(unittest.TestCase):
    def test_success_keeps_original_response_hash_and_does_not_export_prices(self):
        result = review()
        self.assertEqual(result["status"], "WTI_EIA_GAP_REVIEW_PASSED_READ_ONLY")
        self.assertEqual(result["official_observations_in_window"], 3)
        self.assertEqual(result["matched_dates_and_prices"], 2)
        self.assertEqual(result["missing_source_dates_after_cutoff"], 1)
        self.assertEqual(result["source_only_observed_for_dates"], ["2026-10-14"])
        self.assertEqual(result["source_original_html_sha256"], "a" * 64)
        self.assertEqual(result["operator_supplied_local_reference_csv_sha256"], "b" * 64)
        self.assertFalse(result["independent_point_in_time_market_data_certified"])
        self.assertFalse(result["backfill_authorized"])
        self.assertEqual(result["database_connections"], 0)
        self.assertEqual(result["database_writes"], 0)
        self.assertEqual(result["real_orders"], 0)
        self.assertFalse(result["schedule_enabled"])
        self.assertNotIn("91.10", json.dumps(result))

    def test_missing_before_cutoff_fails_even_if_missing_count_matches(self):
        # User supplies a cutoff date but has a gap *before* that cutoff.
        ref = {FIRST: Decimal("91.10")}
        with self.assertRaises(ValueError):
            review(ref=ref, reference_cutoff=LAST, expected_missing=2)

    def test_local_reference_price_mismatch_fails_closed(self):
        ref = reference()
        ref[FIRST] = Decimal("95.55")
        with self.assertRaisesRegex(ValueError, "integrity"):
            review(ref=ref)

    def test_mismatched_expected_missing_count_fails(self):
        with self.assertRaisesRegex(ValueError, "integrity"):
            review(expected_missing=2)

    def test_frozen_release_changed_fails_without_backdating(self):
        with self.assertRaisesRegex(ValueError, "release differs"):
            review(expected_release=date(2026, 10, 16))
        with self.assertRaisesRegex(ValueError, "chronology"):
            review(s=replace(official(), downloaded_at=datetime(
                2026, 10, 14, 12, tzinfo=timezone.utc)))

    def test_wrong_source_retrieval_sha_or_local_sha_rejected(self):
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            review(expected_source_sha256="f" * 64)
        with self.assertRaisesRegex(ValueError, "fingerprints"):
            review(reference_sha256="not-a-valid-hash")
        with self.assertRaisesRegex(ValueError, "WTI"):
            review(s=replace(official(),
                             instrument_code=SOURCES["brent"][0]))

    def test_source_window_is_explicitly_complete(self):
        with self.assertRaisesRegex(ValueError, "does not cover"):
            review(s=replace(official(), observations=official().observations[1:]))
        with self.assertRaisesRegex(ValueError, "does not cover"):
            review(s=replace(official(), observations=official().observations[:-1]))

    def test_reference_must_end_at_selected_cutoff(self):
        ref = reference()
        ref[LAST] = Decimal("93.12")
        with self.assertRaisesRegex(ValueError, "cutoff"):
            review(ref=ref)

    def test_invalid_contract_window_fails(self):
        with self.assertRaisesRegex(ValueError, "ordered"):
            review(window_first=CUTOFF)
        with self.assertRaisesRegex(ValueError, "positive"):
            review(expected_missing=0)

    def test_cli_report_is_aggregate_and_uses_only_public_wti(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "private-file-path-not-in-report.csv"
            path.write_text(
                "instrument_code,observed_for,close_price\n"
                "WTI_EIA_USD_BBL,2026-10-12,91.10\n"
                "WTI_EIA_USD_BBL,2026-10-13,92.11\n",
                encoding="utf-8")
            stdout = StringIO()
            with patch.object(wti, "fetch_official", return_value=official()) as mock:
                with redirect_stdout(stdout):
                    code = wti.main([
                        "--reference-csv", str(path),
                        "--first-observed-for", "2026-10-12",
                        "--last-observed-for", "2026-10-14",
                        "--last-stored-observed-for", "2026-10-13",
                        "--expected-source-release", "2026-10-15",
                        "--expected-missing", "1"])
            self.assertEqual(code, 0)
            self.assertEqual(mock.call_args.args[0], "wti")
            response = json.loads(stdout.getvalue())
            self.assertEqual(response["matched_dates_and_prices"], 2)
            for restricted in ("91.10", "92.11", folder,
                               "postgresql://", "NEON_DATABASE_URL"):
                self.assertNotIn(restricted, stdout.getvalue())

    def test_invalid_local_csv_fails_before_issuing_network_request(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "secret-location.csv"
            path.write_text("invalid sensitive file", encoding="utf-8")
            stderr = StringIO()
            with patch.object(wti, "fetch_official") as fake:
                with redirect_stderr(stderr):
                    result = wti.main([
                        "--reference-csv", str(path),
                        "--first-observed-for", "2026-10-12",
                        "--last-observed-for", "2026-10-14",
                        "--last-stored-observed-for", "2026-10-13",
                        "--expected-source-release", "2026-10-15",
                        "--expected-missing", "1"])
            self.assertEqual(result, 2)
            fake.assert_not_called()
            self.assertNotIn(folder, stderr.getvalue())
            self.assertEqual(stderr.getvalue().strip(),
                             "WTI_COVERAGE_REVIEW_FAILED: ValueError")

    def test_frozen_gap_scales_without_publishing_raw_quotes(self):
        first = date(2026, 7, 1)
        cutoff = date(2026, 7, 20)
        source_days = [first + timedelta(days=i) for i in range(60)]
        official_spots = tuple(
            Spot(d, Decimal(100 + i)) for i, d in enumerate(source_days)
        )
        last = source_days[-1]
        stored = {s.observed_on: s.price for s in official_spots
                  if s.observed_on <= cutoff}
        result = wti.review_gap(
            replace(official(), observations=official_spots,
                    release_day=last + timedelta(days=1),
                    downloaded_at=datetime(2026, 10, 18, tzinfo=timezone.utc)),
            stored, window_first=first, window_last=last,
            reference_cutoff=cutoff, expected_release=last + timedelta(days=1),
            expected_missing=len(official_spots) - len(stored),
            reference_sha256="b"*64)
        self.assertEqual(result["missing_source_dates_after_cutoff"],
                         len(official_spots) - len(stored))
        self.assertEqual(result["source_value_mismatches"], 0)
        self.assertNotIn("102", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
