"""Offline contract for an original NBP public annual Table A CSV snapshot."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import unittest

from scripts.nbp_table_a_archive_v09 import (
    ARCHIVE_URL, ArchiveBlocked, inspect_archive, observe_once,
)


NOW = datetime(2026, 11, 23, tzinfo=timezone.utc)


def csv_sample(*, duplicate=False, bad_rate=False, bad_table=False):
    return ("data;1USD;1EUR;nr tabeli;pełny numer tabeli;\r\n"
            ";dolar amerykański;euro;;\r\n"
            "20260901;3,7371;4,3328;169;169/A/NBP/2026;\r\n"
            f"20260902;{'nan' if bad_rate else '3,7423'};4,3311;"
            f"170;{'170/B/NBP/2026' if bad_table else '170/A/NBP/2026'};\r\n"
            + ("20260902;3,7423;4,3311;170;170/A/NBP/2026;\r\n"
               if duplicate else "")).encode("cp1250")


class NBPArchiveTests(unittest.TestCase):
    def test_official_annual_csv_footer_after_blank_line_is_not_market_data(self):
        fixture = csv_sample() + (
            "\r\nkod ISO;USD;EUR;X\r\n"
            "nazwa waluty;dolar;euro;X\r\n"
            "liczba jednostek;1;1;X\r\n").encode("cp1250")
        out = inspect_archive(fixture, observed_at=NOW)
        self.assertEqual(out["september_2026_days"], 2)

    def test_original_csv_validates_and_preserves_raw_byte_sha(self):
        raw = csv_sample()
        result = inspect_archive(raw, observed_at=NOW)
        self.assertEqual(result["source_url"], ARCHIVE_URL)
        self.assertEqual(result["original_csv_sha256"], sha256(raw).hexdigest())
        self.assertEqual(result["september_2026_days"], 2)
        self.assertEqual(result["first_publication_date"], "2026-09-01")
        self.assertEqual(result["last_publication_date"], "2026-09-02")
        self.assertEqual(result["latest_usdpln_mid"], "3.7423")
        self.assertEqual(result["latest_eurpln_mid"], "4.3311")
        self.assertFalse(result["historical_pit_certified"])
        self.assertEqual(result["financial_operations"], 0)
        self.assertNotIn("raw_rows", result)

    def test_duplicate_dates_invalid_values_or_tables_fail_closed(self):
        for changes in ({"duplicate": True}, {"bad_rate": True},
                        {"bad_table": True}):
            with self.subTest(**changes), self.assertRaises(ArchiveBlocked):
                inspect_archive(csv_sample(**changes), observed_at=NOW)

    def test_explicit_one_shot_fetch_only(self):
        with self.assertRaisesRegex(ArchiveBlocked, "EXPLICIT"):
            observe_once(fetch=None, clock=lambda: NOW)
        urls = []
        def fetch(url):
            urls.append(url)
            return csv_sample()
        self.assertEqual(observe_once(fetch=fetch, clock=lambda: NOW)[
            "september_2026_days"], 2)
        self.assertEqual(urls, [ARCHIVE_URL])


if __name__ == "__main__":
    unittest.main()
