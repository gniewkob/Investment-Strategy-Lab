"""Offline tests: scheduled NBP output never accesses Neon or trading APIs."""
import hashlib
import json
import unittest
from datetime import datetime, timezone

from scripts.nbp_lab_daily_source import daily_source

NOW = datetime(2026, 11, 6, 5, tzinfo=timezone.utc)
FX = [{"table": "A", "no": "202/A/NBP/2026",
       "effectiveDate": "2026-11-05",
       "rates": [{"code": "USD", "mid": 3.9011},
                 {"code": "EUR", "mid": 4.3211}]}]
GOLD = [{"data": "2026-11-05", "cena": 501.43}]


def fixture(url):
    return json.dumps(GOLD if "/cenyzlota/" in url else FX).encode()


class NBPDailySourceTests(unittest.TestCase):
    def test_bounded_live_receipt_and_hash(self):
        meta, sql = daily_source(NOW, fetch=fixture, clock=lambda: NOW)
        self.assertEqual(meta["range_start"], "2026-10-06")
        self.assertEqual(meta["range_end"], "2026-11-06")
        self.assertEqual(meta["captured_rows"], 3)
        self.assertEqual(meta["by_series"], {"eurpln": 1, "usdpln": 1, "gold": 1})
        self.assertEqual(hashlib.sha256(sql.encode()).hexdigest(),
                         meta["compiled_sql_sha256"])
        self.assertEqual(meta["financial_operations"], 0)
        self.assertEqual(meta["paper_events_created"], 0)
        self.assertTrue(meta["source_data_not_total_return"])
        self.assertIn("INSERT INTO investment_lab.price_observations", sql)
        self.assertNotIn("INSERT INTO investment_lab.paper_events", sql)
        self.assertNotIn("DELETE FROM investment_lab.", sql)

    def test_invalid_lookback_and_clock_are_rejected(self):
        for days in (-1, 0, 6, 91, 100):
            with self.subTest(days=days), self.assertRaises(ValueError):
                daily_source(NOW, fetch=fixture, clock=lambda: NOW,
                             lookback_days=days)
        with self.assertRaises(ValueError):
            daily_source(datetime(2026, 11, 6), fetch=fixture,
                         clock=lambda: NOW)

    def test_source_failure_blocks_compilation(self):
        def failing(url):
            if "/cenyzlota/" in url:
                raise OSError("upstream unavailable")
            return fixture(url)
        with self.assertRaises(OSError):
            daily_source(NOW, fetch=failing, clock=lambda: NOW)

    def test_future_publication_rejected(self):
        def future(url):
            if "/cenyzlota/" in url:
                return json.dumps([{"data": "2026-11-07", "cena": 500}]).encode()
            return fixture(url)
        with self.assertRaises(ValueError):
            daily_source(NOW, fetch=future, clock=lambda: NOW)


if __name__ == "__main__":
    unittest.main()
