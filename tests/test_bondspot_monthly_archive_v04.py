"""Offline fail-closed coverage for official BondSpot monthly close archive."""
from datetime import datetime, timezone
import unittest
from urllib.parse import parse_qs, urlsplit

from scripts.bondspot_monthly_archive_v04 import collect, parse_close, _url


NOW = datetime(2026, 11, 6, 14, tzinfo=timezone.utc)


def stub(url):
    query = parse_qs(urlsplit(url).query)
    day = query["date"][0]
    date = f"{day[:4]}-{day[4:6]}-{day[6:]}"
    if date in ("2024-02-29", "2024-03-28"):
        return f"""<html><body>TBSP.Index
        <table><tr><th>Date</th><th>Opening value</th>
        <th>Closing value</th></tr>
        <tr><td>{date}</td><td>1966.95</td><td>1965.16</td></tr>
        </table></body></html>""".encode()
    return b"<html><h1>TBSP.Index archive</h1><p>No closing value</p></html>"


class BondSpotMonthlyArchiveTests(unittest.TestCase):
    def test_parses_exact_date_closing_not_current_headline(self):
        day = __import__("datetime").date(2024, 2, 16)
        raw = b"""<html>2026-11-06 2222.00 2221.50
           <table><tr><td>2024-02-16</td>
           <td>1966.95</td><td>1965.16</td></tr></table></html>"""
        self.assertEqual(parse_close(day, raw), "1965.16")
        self.assertIsNone(parse_close(day, b"<html>No value</html>"))

    def test_collects_two_actual_dates_in_consecutive_months(self):
        o = collect("2024-02", "2024-03", fetch=stub, clock=lambda: NOW)
        self.assertEqual(o["months"], 2)
        self.assertEqual([r["observed_for"] for r in o["monthly"]],
                         ["2024-02-29", "2024-03-28"])
        self.assertEqual([r["value"] for r in o["monthly"]],
                         ["1965.16", "1965.16"])
        self.assertTrue(all(r["instrument_kind"] == "NON_TRADABLE_INDEX"
                            for r in o["monthly"]))
        self.assertFalse(o["historical_first_available_verified"])
        self.assertFalse(o["executable_price_verified"])
        self.assertEqual(o["backtest"], "NOT_RUN_PENDING_SOURCE_VALIDATION")
        self.assertEqual(o["financial_operations"], 0)
        self.assertEqual(o, collect("2024-02", "2024-03",
                                    fetch=stub, clock=lambda: NOW))

    def test_does_not_invent_holiday_or_unavailable_close(self):
        with self.assertRaisesRegex(ValueError, "NO_VERIFIED_BONDSPOT_CLOSE"):
            collect("2024-04", "2024-04", fetch=stub, clock=lambda: NOW)

    def test_rejects_ambiguous_duplicate_day_and_bad_value(self):
        d = __import__("datetime").date(2024, 2, 16)
        raw = b"<table>2024-02-16 1966.95 1965.16 2024-02-16 1966.95 1965.15</table>"
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            parse_close(d, raw)
        with self.assertRaisesRegex(ValueError, "invalid TBSP closing value"):
            parse_close(d, b"<table>2024-02-16 1966.95 0000.00</table>")

    def test_source_query_pins_official_archive(self):
        d = __import__("datetime").date(2024, 2, 16)
        self.assertEqual(_url(d),
            "https://www.bondspot.pl/tbsp_index_archive_en?date=20240216&month=02&year=2024")

    def test_rejects_future_month_long_request_and_clock(self):
        for a,b in (("2026-11", "2026-11"), ("2018-01", "2026-10"),
                    ("2025-03","2024-04"), ("2024-00", "2024-01")):
            with self.subTest(a=a,b=b), self.assertRaises(ValueError):
                collect(a,b,fetch=stub,clock=lambda: NOW)
        with self.assertRaisesRegex(ValueError, "clock"):
            collect("2024-02","2024-02",fetch=stub,
                    clock=lambda:datetime(2026,11,6))

    def test_no_network_errors_silently_interpreted_as_missing(self):
        def fail(url):
            raise OSError("Network unavailable")
        with self.assertRaises(OSError):
            collect("2024-02","2024-02",fetch=fail,clock=lambda:NOW)


if __name__ == "__main__":
    unittest.main()
