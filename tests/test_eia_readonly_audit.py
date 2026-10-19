"""Entirely synthetic tests for the read-only EIA source/coverage audit."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib
import json
import unittest

from scripts import eia_readonly_audit as subject
from src.isl_v2.eia_sources import Snapshot, Spot, SourceFormatError

NOW = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)
CODE = "WTI_EIA_USD_BBL"
URL = "https://www.eia.gov/dnav/pet/hist/RWTCd.htm"


def snapshot():
    return Snapshot(
        CODE, "eia_wti_daily", URL, "a" * 64,
        date(2026, 10, 15), NOW,
        (Spot(date(2026, 10, 12), Decimal("98.73")),
         Spot(date(2026, 10, 13), Decimal("100.86")),
         Spot(date(2026, 10, 14), Decimal("101.91"))), 3,
    )


def official_html():
    def row(label, prices):
        return "<tr><td>" + label + "</td>" + "".join(
            "<td>" + p + "</td>" for p in prices) + "</tr>"
    table = "".join((
        row("2026 Sep-21 to Sep-25", ["95", "96", "97", "98", "99"]),
        row("2026 Sep-28 to Oct- 2", ["100", "101", "102", "103", "104"]),
        row("2026 Oct- 5 to Oct- 9", ["105", "106", "107", "108", "109"]),
        row("2026 Oct-12 to Oct-16", ["110", "111", "112", "", ""]),
    ))
    return ("<html><table>" + table + "</table>"
            "<p>Release Date: 10/15/2026</p>"
            "<p>Next Release Date: 10/21/2026</p></html>").encode()


class FakeResponse:
    def __init__(self, data=None, final_url=URL, media="text/html"):
        self.data = official_html() if data is None else data
        self.final_url = final_url
        self.headers = {"Content-Type": media}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return self.final_url

    def read(self, size):
        return self.data[:size]


def csv_file(folder, content):
    p = Path(folder) / "sample.csv"
    p.write_text(content, encoding="utf-8")
    return p


class ReadOnlyEIAAuditTests(unittest.TestCase):
    def test_full_date_and_exact_decimal_value_match(self):
        sample = snapshot()
        reference = {item.observed_on: item.price for item in sample.observations}
        report = subject.compare_dates_prices(sample, reference)
        self.assertEqual(report["matching_dates_and_values"], 3)
        self.assertEqual(report["source_missing_from_reference"], 0)
        self.assertEqual(report["price_mismatches"], 0)
        self.assertEqual(report["reference_dates_absent_from_source"], 0)
        self.assertEqual(report["original_source_response_sha256"], "a" * 64)
        self.assertFalse(report["historical_publication_vintages_verified"])
        for key in ("db_reads", "db_writes", "real_orders", "allocation_changes"):
            self.assertEqual(report[key], 0)

    def test_missing_day_mismatch_extra_source_day_and_out_of_scope(self):
        s = snapshot()
        reference = {
            date(2026, 10, 12): Decimal("98.73"),
            date(2026, 10, 13): Decimal("100.85"),
            date(2026, 10, 11): Decimal("20"),  # Outside official window.
        }
        report = subject.compare_dates_prices(s, reference)
        self.assertEqual(report["matching_dates_and_values"], 1)
        self.assertEqual(report["source_missing_from_reference"], 1)
        self.assertEqual(report["missing_date_keys"], ["2026-10-14"])
        self.assertEqual(report["price_mismatches"], 1)
        self.assertEqual(report["mismatched_date_keys"], ["2026-10-13"])
        self.assertEqual(report["reference_observations_outside_window"], 1)
        self.assertNotIn("98.73", json.dumps(report))

    def test_date_only_extra_in_middle_of_official_window(self):
        s = snapshot()
        # An official price on Oct 13 is absent here, but the reference also
        # carries a calendar day for which EIA has no quote.
        official = Snapshot(s.instrument_code, s.source_code, s.url,
                            s.sha256_hex, s.release_day, s.downloaded_at,
                            (s.observations[0], s.observations[2]), 2)
        reference = {date(2026, 10, 12): Decimal("98.73"),
                     date(2026, 10, 13): Decimal("3"),
                     date(2026, 10, 14): Decimal("101.91")}
        report = subject.compare_dates_prices(official, reference)
        self.assertEqual(report["reference_dates_absent_from_source"], 1)
        self.assertEqual(report["extra_date_keys"], ["2026-10-13"])

    def test_csv_reader_rejects_extra_columns_and_mixed_instruments(self):
        with TemporaryDirectory() as td:
            p = csv_file(td, "instrument_code,observed_for,close_price,account_id\n"
                          "WTI_EIA_USD_BBL,2026-10-12,1,private\n")
            with self.assertRaises(ValueError):
                subject.read_local_reference(p, CODE)
            p = csv_file(td, "instrument_code,observed_for,close_price\n"
                          "BTC-USD,2026-10-12,100\n")
            with self.assertRaises(ValueError):
                subject.read_local_reference(p, CODE)

    def test_csv_reader_rejects_duplicate_nonfinite_and_bad_dates(self):
        with TemporaryDirectory() as td:
            head = "instrument_code,observed_for,close_price\n"
            for cells in (
                "WTI_EIA_USD_BBL,2026-10-12,100\nWTI_EIA_USD_BBL,2026-10-12,101\n",
                "WTI_EIA_USD_BBL,2026-10-12,NaN\n",
                "WTI_EIA_USD_BBL,2026-10-12,0\n",
                "WTI_EIA_USD_BBL,2026-99-12,100\n",
            ):
                p = csv_file(td, head + cells)
                with self.assertRaises(ValueError):
                    subject.read_local_reference(p, CODE)

    def test_csv_exact_field_contract_succeeds(self):
        with TemporaryDirectory() as td:
            p = csv_file(td, "instrument_code,observed_for,close_price\n"
                          "WTI_EIA_USD_BBL,2026-10-12,98.7300\n"
                          "WTI_EIA_USD_BBL,2026-10-14,101.91\n")
            got = subject.read_local_reference(p, CODE)
            self.assertEqual(len(got), 2)
            self.assertEqual(got[date(2026, 10, 12)], Decimal("98.7300"))

    def test_reference_sha256_is_of_exact_parsed_input_bytes(self):
        with TemporaryDirectory() as td:
            original = (
                "instrument_code,observed_for,close_price\\r\\n"
                "WTI_EIA_USD_BBL,2026-10-12,98.7300\\r\\n"
                "WTI_EIA_USD_BBL,2026-10-14,101.91\\r\\n"
            ).replace("\\r", "\r").replace("\\n", "\n").encode("utf-8")
            p = Path(td) / "reference.csv"
            p.write_bytes(original)
            data, digest = subject.read_local_reference_with_digest(p, CODE)
            self.assertEqual(digest, hashlib.sha256(original).hexdigest())
            self.assertEqual(data[date(2026, 10, 12)], Decimal("98.7300"))
            self.assertEqual(subject.read_local_reference(p, CODE), data)

    def test_local_csv_hard_size_limit_fails_closed(self):
        with TemporaryDirectory() as td:
            p = Path(td) / "too-big.csv"
            p.write_bytes(b"x" * (subject.MAX_LOCAL_CSV_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "too large"):
                subject.read_local_reference_with_digest(p, CODE)

    def test_csv_extra_row_field_and_noncanonical_date_fail_closed(self):
        with TemporaryDirectory() as td:
            header = "instrument_code,observed_for,close_price\\n".replace("\\n", "\n")
            invalid_rows = (
                "WTI_EIA_USD_BBL,2026-10-12,98.73,EXTRA\\n",
                "WTI_EIA_USD_BBL,20261012,98.73\\n",
                "WTI_EIA_USD_BBL,2026-10-12\\n",
            )
            for invalid in invalid_rows:
                p = Path(td) / "strict.csv"
                p.write_text(header + invalid.replace("\\n", "\n"), encoding="utf-8")
                with self.assertRaises(ValueError):
                    subject.read_local_reference_with_digest(p, CODE)

    def test_allowed_https_source_fetch_and_original_bytes_hash(self):
        data = official_html()
        def fake_open(request, timeout):
            self.assertEqual(request.full_url, URL)
            self.assertEqual(timeout, 30)
            return FakeResponse(data)
        got = subject.fetch_official("wti", NOW, opener=fake_open,
                                     completion_clock=lambda: NOW + timedelta(seconds=2))
        self.assertEqual(got.sha256_hex, hashlib.sha256(data).hexdigest())
        self.assertEqual(len(got.observations), 18)
        self.assertEqual(got.release_day, date(2026, 10, 15))
        self.assertEqual(got.downloaded_at, NOW + timedelta(seconds=2))
        self.assertTrue(subject.source_summary(got)["db_writes"] == 0)

    def test_audit_acquisition_clock_is_post_response_and_cannot_backdate(self):
        steps = []
        class MonitoredResponse(FakeResponse):
            def read(self, size):
                steps.append("read")
                return super().read(size)
            def __exit__(self,*args):
                steps.append("closed")
                return False
        def end_clock():
            steps.append("completed")
            return NOW + timedelta(seconds=3)
        got = subject.fetch_official(
            "wti", NOW, opener=lambda *a,**k: MonitoredResponse(),
            completion_clock=end_clock)
        self.assertEqual(steps,["read","closed","completed"])
        self.assertEqual(got.downloaded_at, NOW + timedelta(seconds=3))

        for invalid in (
            NOW - timedelta(seconds=1),
            NOW + timedelta(minutes=3),
            NOW.replace(tzinfo=None),
        ):
            with self.assertRaisesRegex(SourceFormatError,"clock"):
                subject.fetch_official(
                    "wti", NOW, opener=lambda *a,**k: FakeResponse(),
                    completion_clock=lambda: invalid)
        with self.assertRaisesRegex(SourceFormatError,"start"):
            subject.fetch_official(
                "wti",NOW.replace(tzinfo=None),
                opener=lambda *a,**k: FakeResponse())

    def test_http_redirect_or_bad_media_type_fails_closed(self):
        for response in (
            FakeResponse(final_url="https://example.net/price"),
            FakeResponse(media="application/octet-stream"),
        ):
            with self.assertRaises(SourceFormatError):
                subject.fetch_official(
                    "wti", NOW, opener=lambda *_args, **_kwargs: response)

    def test_csv_bad_input_prevents_network_access_and_path_leak(self):
        with TemporaryDirectory() as td:
            p = csv_file(td, "secret-never-emit")
            stderr = StringIO()
            with patch.object(subject, "fetch_official") as fake_fetch:
                with redirect_stderr(stderr):
                    code = subject.main(["--source", "wti",
                                         "--reference-csv", str(p)])
            self.assertEqual(code, 2)
            fake_fetch.assert_not_called()
            self.assertNotIn(str(p), stderr.getvalue())
            self.assertNotIn("secret-never-emit", stderr.getvalue())

    def test_cli_summary_never_prints_raw_quote_or_source_html(self):
        sample = snapshot()
        stdout = StringIO()
        with patch.object(subject, "fetch_official", return_value=sample):
            with redirect_stdout(stdout):
                code = subject.main(["--source", "wti"])
        self.assertEqual(code, 0)
        report = json.loads(stdout.getvalue())
        self.assertEqual(report["validated_observations"], 3)
        self.assertNotIn("98.73", stdout.getvalue())
        self.assertNotIn("101.91", stdout.getvalue())
        self.assertEqual(report["db_writes"], 0)


if __name__ == "__main__":
    unittest.main()
