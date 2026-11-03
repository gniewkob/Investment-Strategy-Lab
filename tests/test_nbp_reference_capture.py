import json
import unittest
from datetime import datetime, timezone

from scripts.nbp_reference_capture import capture


class NBPCaptureTests(unittest.TestCase):
    def setUp(self):
        self.fx = [{"table": "A", "no": "001/A/2020", "effectiveDate": "2020-01-02", "rates": [{"code": "USD", "mid": 3.8}, {"code": "EUR", "mid": 4.2}]}]
        self.gold = [{"data": "2020-01-02", "cena": 200.0}]

    def run_capture(self):
        def fetch(url):
            return json.dumps(self.gold if "cenyzlota" in url else self.fx).encode()
        return capture("2020-01-01", "2020-01-31", fetch, lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_real_shape_produces_uncertified_receipt(self):
        result = self.run_capture()
        self.assertEqual(result["series"]["usdpln"][0]["value"], "3.8")
        self.assertIsNone(result["series"]["gold"][0]["available_at"])
        self.assertEqual(result["market_data_readiness"], "INSUFFICIENT_DATA")
        self.assertEqual(result["paper_events_created"], 0)
        self.assertEqual(len(result["receipts"]["fx"]["sha256"]), 64)

    def test_missing_currency_and_duplicate_dates_fail(self):
        self.fx[0]["rates"].pop()
        with self.assertRaises(ValueError):
            self.run_capture()
        self.fx[0]["rates"].append({"code": "EUR", "mid": 4.2})
        self.gold.append(self.gold[0])
        with self.assertRaises(ValueError):
            self.run_capture()

    def test_invalid_value_and_range_fail(self):
        self.gold[0]["cena"] = 0
        with self.assertRaises(ValueError):
            self.run_capture()
        with self.assertRaises(ValueError):
            capture("2020-01-01", "2020-04-04", lambda _: b"[]")

    def test_upstream_failure_is_not_empty_success(self):
        def fetch(_):
            raise OSError("source unavailable")
        with self.assertRaises(OSError):
            capture("2020-01-01", "2020-01-02", fetch)
