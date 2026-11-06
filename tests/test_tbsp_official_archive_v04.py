"""Offline BondSpot archive parser tests: no network, no trades."""
from __future__ import annotations
from datetime import datetime, timezone
import unittest

from scripts.tbsp_official_archive_v04 import collect, _url, _parse, _day_row
from scripts.tbsp_archive_merge_v04 import merge, check_chunk

NOW=datetime(2026,11,6,13,tzinfo=timezone.utc)

def fixture(url: str, *, missing=False, duplicate=False) -> bytes:
    from urllib.parse import urlsplit,parse_qs
    q=parse_qs(urlsplit(url).query)
    month=q["month"][0]; year=q["year"][0]
    d=q.get("date",[""])[0]
    if d:
        day=d[:4]+"-"+d[4:6]+"-"+d[6:]
        values="2024.22" if month=="03" else "2021.45"
        row=(f"<table><tr><th>Data</th><th>Wartość otwarcia</th>"
             f"<th>Wartość zamknięcia</th></tr>"
             f"<tr><td>{day}</td><td>2020.22</td><td>{values}</td></tr></table>")
        if duplicate:
            row+=f"<tr><td>{day}</td><td>2020.22</td><td>{values}</td></tr>"
    else:
        row="" if missing else (
            f"<a href='?date={year}{month}20&month={month}&year={year}'>20</a>"
            f"<a href='?date={year}{month}28&month={month}&year={year}'>28</a>"
            "<a href='https://other.example/?date=20250331'>31</a>"
        )
    return ("<html><body><h1>TBSP.Index</h1>"
            "<h2>Dane archiwalne TBSP.Index</h2>"+row+"</body></html>").encode()

class OfficialBondSpotArchiveTests(unittest.TestCase):
    def test_months_select_last_official_day_and_preserve_raw_hash(self):
        calls=[]
        def tracked(url):
            calls.append(url)
            return fixture(url)
        out=collect("2025-02","2025-03",fetch=tracked,clock=lambda:NOW)
        self.assertEqual(out["months"],2)
        self.assertEqual(len(calls),4)
        self.assertEqual([r["observed_for"] for r in out["observations"]],
                         ["2025-02-28","2025-03-28"])
        self.assertEqual([r["level"] for r in out["observations"]],
                         ["2021.45","2024.22"])
        self.assertTrue(all(len(r["dated_sha256"])==64 for r in out["observations"]))
        self.assertTrue(all(len(r["calendar_sha256"])==64 for r in out["observations"]))
        self.assertEqual(out["instrument_kind"],"NON_TRADABLE_INDEX")
        self.assertEqual(out["basis"],"BOND_TOTAL_RETURN_BENCHMARK_INDEX")
        self.assertIsNone(out["observations"][0]["historical_first_usable_at"])
        self.assertFalse(out["historical_pit_certified"])
        self.assertEqual(out["backtest"],"NOT_RUN_SOURCE_ONLY")
        self.assertEqual(out["paper_events_created"],0)
        self.assertEqual(out["financial_operations"],0)

    def test_unknown_or_empty_month_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"no dated"):
            collect("2025-01","2025-01",fetch=lambda u:fixture(u,missing=True),clock=lambda:NOW)

    def test_duplicate_close_row_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"not exactly one"):
            collect("2025-03","2025-03",
                    fetch=lambda u:fixture(u,duplicate=True),clock=lambda:NOW)

    def test_unrecognized_page_fails(self):
        with self.assertRaisesRegex(ValueError,"TBSP"):
            collect("2025-03","2025-03",fetch=lambda u:b"<html>bad</html>",
                    clock=lambda:NOW)

    def test_https_url_month_constraints_and_future(self):
        self.assertEqual(_url("2025-03","20250328"),
                         "https://www.bondspot.pl/tbsp_index_archiwum?month=03&year=2025&date=20250328")
        for first,last in [("2027-01","2027-01"),("2025-13","2025-13"),
                           ("2025-07","2025-01"),("2010-01","2026-10")]:
            with self.subTest(first=first,last=last),self.assertRaises(ValueError):
                collect(first,last,fetch=fixture,clock=lambda:NOW)

    def test_future_clock_in_historical_month(self):
        with self.assertRaisesRegex(ValueError,"completed months"):
            collect("2026-11","2026-11",fetch=fixture,clock=lambda:NOW)

    def test_merge_two_source_provenance_chunks(self):
        a=collect("2025-02","2025-02",fetch=fixture,clock=lambda:NOW)
        b=collect("2025-03","2025-03",fetch=fixture,clock=lambda:NOW)
        merged=merge([b,a],"2025-02","2025-03")
        self.assertEqual(merged["monthly_count"],2)
        self.assertEqual(len(merged["chunk_receipts"]),2)
        self.assertEqual(merged["monthly_observations"][0]["month"],"2025-02")
        self.assertEqual(merged["monthly_observations"][-1]["month"],"2025-03")
        self.assertEqual(len(merged["evidence_sha256"]),64)
        self.assertEqual(merged["backtest"],"NOT_RUN_SOURCE_ONLY")
        self.assertFalse(merged["historical_pit_certified"])
        self.assertFalse(merged["trading_price_proven"])
        self.assertEqual(merged["financial_operations"],0)

    def test_merge_rejects_modified_source_receipt(self):
        a=collect("2025-02","2025-02",fetch=fixture,clock=lambda:NOW)
        a["observations"][0]["level"]="9999.99"
        with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
            check_chunk(a)

    def test_merge_rejects_missing_and_overlapping_months(self):
        a=collect("2025-02","2025-02",fetch=fixture,clock=lambda:NOW)
        b=collect("2025-03","2025-03",fetch=fixture,clock=lambda:NOW)
        with self.assertRaisesRegex(ValueError,"gap or overlap"):
            merge([a,a],"2025-02","2025-03")
        with self.assertRaisesRegex(ValueError,"cover"):
            merge([a],"2025-02","2025-03")
        with self.assertRaisesRegex(ValueError,"gap or overlap"):
            merge([a,b],"2025-02","2025-04")

    def test_nonpositive_or_malformed_close_rejected(self):
        def corrupted(u):
            return fixture(u).replace(b"2024.22",b"0.00")
        with self.assertRaisesRegex(ValueError,"invalid TBSP"):
            collect("2025-03","2025-03",fetch=corrupted,clock=lambda:NOW)

if __name__=="__main__":
    unittest.main()
