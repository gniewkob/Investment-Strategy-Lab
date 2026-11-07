"""Offline deterministic tests for 60-month NBP reference-only archive."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import re
import unittest

from scripts.nbp_long_history_monthly import collect, _windows

NOW = datetime(2026, 11, 6, 13, tzinfo=timezone.utc)
RANGE = re.compile(r"/(\d{4}-\d{2}-\d{2})/(\d{4}-\d{2}-\d{2})/")


def fixture(url: str, *, skip_month: str | None = None,
            missing_usd: bool = False, duplicate: bool = False) -> bytes:
    m = RANGE.search(url)
    assert m, url
    start, stop = date.fromisoformat(m[1]), date.fromisoformat(m[2])
    dates = []
    current = start
    while current <= stop:
        if current.strftime("%Y-%m") != skip_month:
            dates.append(current)
        current += timedelta(days=7)
    if "/cenyzlota/" in url:
        out = [{"data": d.isoformat(), "cena": str(200+(d.year-2020)*10+d.month)}
               for d in dates]
    else:
        out = [
            {"table": "A", "no": f"{i}/A/NBP/{d.year}",
             "effectiveDate": d.isoformat(),
             "rates": ([{"code": "EUR", "mid": "4.30"}] if missing_usd else
                       [{"code": "USD", "mid": "3.85"},
                        {"code": "EUR", "mid": "4.30"}])}
            for i, d in enumerate(dates, 1)
        ]
    if duplicate and out:
        out.append(out[0])
    return json.dumps(out, sort_keys=True).encode()


class NBPFiveYearHistoryTests(unittest.TestCase):
    def run_history(self, fetch=fixture, start="2021-11", end="2026-10"):
        return collect(start, end, fetch=fetch, clock=lambda: NOW)

    def test_five_year_60_months_qualified_reference_only(self):
        output = self.run_history()
        self.assertEqual(output["calendar_months"], 60)
        self.assertGreaterEqual(output["source_window_count"], 20)
        self.assertLessEqual(output["source_window_count"], 22)
        self.assertEqual(output["source_request_count"],
                         output["source_window_count"]*2)
        self.assertEqual(output["monthly_counts"],
                         {"usdpln": 60, "eurpln": 60, "gold": 60})
        self.assertEqual(len(output["source_windows"]),
                         output["source_window_count"])
        self.assertEqual(len(output["evidence_sha256"]), 64)
        self.assertFalse(output["historical_vintage_verified"])
        self.assertFalse(output["historical_first_publication_time_verified"])
        self.assertFalse(output["point_in_time_backtest_authorized"])
        self.assertEqual(output["backtest"], "NOT_RUN_REFERENCE_ONLY")
        self.assertEqual(output["financial_operations"], 0)
        self.assertEqual(output["paper_events_created"], 0)
        self.assertEqual(output["series_contract"]["gold"]["return_basis"],
                         "PRICE_ONLY")
        self.assertEqual(output["series_contract"]["usdpln"]["return_basis"],
                         "FX_RATE")
        for name, rows in output["monthly_observations"].items():
            self.assertEqual(len(rows), 60)
            self.assertEqual(rows[0]["month"], "2021-11")
            self.assertEqual(rows[-1]["month"], "2026-10")
            self.assertTrue(all(x["observed_for"][:7] == x["month"]
                                for x in rows))
            self.assertTrue(all(x["source_url"].startswith(
                            "https://api.nbp.pl/api/") for x in rows))
            self.assertTrue(all(len(x["raw_sha256"]) == 64 for x in rows))

    def test_repeat_is_deterministic_and_tamper_changes_digest(self):
        a = self.run_history()
        b = self.run_history()
        self.assertEqual(a, b)

        def tampered(url):
            raw = fixture(url)
            if "/cenyzlota/" in url and "/2024-" in url:
                data = json.loads(raw)
                if data:
                    data[0]["cena"] = "888.8"
                    return json.dumps(data, sort_keys=True).encode()
            return raw

        changed = self.run_history(fetch=tampered)
        self.assertNotEqual(a["evidence_sha256"], changed["evidence_sha256"])

    def test_missing_month_is_never_filled_synthetically(self):
        with self.assertRaisesRegex(ValueError, "lacks published month"):
            self.run_history(fetch=lambda url: fixture(url, skip_month="2024-05"))

    def test_missing_usd_and_duplicate_day_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "exchange rate"):
            self.run_history(fetch=lambda url: fixture(url, missing_usd=True))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.run_history(fetch=lambda url: fixture(url, duplicate=True))

    def test_http_failures_fail_whole_request(self):
        def failing(url):
            if "2023" in url and "/cenyzlota/" in url:
                raise OSError("test NBP unavailable")
            return fixture(url)
        with self.assertRaises(OSError):
            self.run_history(fetch=failing)

    def test_future_or_unbounded_months_rejected_before_network(self):
        cases = [
            ("2027-01", "2027-02"),
            ("2019-01", "2026-10"),
            ("2026-11", "2026-10"),
            ("2012-01", "2012-12"),
            ("2024-00", "2024-01"),
            ("2024-13", "2024-14"),
        ]
        for start, end in cases:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                self.run_history(start=start, end=end)

    def test_requested_windows_are_contiguous_and_maximum_90_days(self):
        windows = _windows(date(2021, 11, 1), date(2026, 10, 31))
        self.assertEqual(windows[0][0], date(2021, 11, 1))
        self.assertEqual(windows[-1][1], date(2026, 10, 31))
        self.assertTrue(all(0 <= (b-a).days < 90 for a,b in windows))
        self.assertTrue(all(windows[i][1]+timedelta(days=1) == windows[i+1][0]
                            for i in range(len(windows)-1)))


if __name__ == "__main__":
    unittest.main()
