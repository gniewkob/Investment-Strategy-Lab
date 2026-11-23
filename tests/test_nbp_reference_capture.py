import hashlib
import json
import unittest
from datetime import datetime, timezone

from scripts.nbp_reference_capture import capture
from scripts.nbp_reference_chunked_v09 import capture_chunked
from scripts.monthly_pit_calendar import assess_calendar


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

    def test_capture_feeds_calendar_without_certifying_or_forward_filling(self):
        captured = self.run_capture()
        report = assess_calendar({"sessions": ["2020-01-02", "2020-01-03"],
                                  "decision_dates": ["2020-01-02", "2020-01-03"],
                                  "series": captured["series"]})
        self.assertIn("gold", report["coverage_by_decision"][0]["missing_series"])
        for name in ("usdpln", "eurpln", "gold"):
            self.assertEqual(report["series"][name]["accepted_rows"], 1)
            selected = report["coverage_by_decision"][1]["available_series"][name]
            self.assertFalse(selected["license_verified"])
            self.assertFalse(selected["historical_vintage_verified"])
        self.assertEqual(captured["series"]["gold"][0]["basis"], "PRICE_ONLY_PLN_PER_GRAM")
        self.assertEqual(report["backtest"], "NOT_RUN")

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

    def test_chunked_capture_preserves_each_original_url_and_byte_hash(self):
        observed = []
        def fetch(url):
            observed.append(url)
            day = url.split("/")[-3]
            if "cenyzlota" in url:
                return json.dumps([{"data": day, "cena": 200}]).encode()
            return json.dumps([{"table": "A", "no": "A/2026", "effectiveDate": day,
                                "rates": [{"code": "USD", "mid": 4},
                                          {"code": "EUR", "mid": 4.5}]}]).encode()
        result = capture_chunked("2026-09-01", "2026-09-30", fetch=fetch,
                                 clock=lambda: datetime(2026, 11, 1, tzinfo=timezone.utc),
                                 chunk_days=10)
        self.assertEqual(len(observed), 6)
        self.assertEqual(len(result["series"]["gold"]), 3)
        self.assertEqual(len(result["receipts"]["fx"]["chunks"]), 3)
        self.assertEqual(result["series"]["gold"][1]["publication_date"], "2026-09-11")
        for kind, code in (("fx", "usdpln"), ("gold", "gold")):
            for index, receipt in enumerate(result["receipts"][kind]["chunks"]):
                row = result["series"][code][index]
                self.assertEqual(row["source_url"], receipt["url"])
                self.assertEqual(row["source_sha256"], receipt["sha256"])
                self.assertEqual(receipt["sha256"], hashlib.sha256(fetch(receipt["url"])).hexdigest())
        self.assertNotIn("sha256", result["receipts"]["fx"])

    def test_chunked_capture_rejects_duplicate_dates_across_original_responses(self):
        def fetch(url):
            day = "2026-09-01"  # Second segment cannot claim the first segment's day.
            if "cenyzlota" in url:
                return json.dumps([{"data": day, "cena": 200}]).encode()
            return json.dumps([{"table": "A", "no": "A/2026", "effectiveDate": day,
                                "rates": [{"code": "USD", "mid": 4},
                                          {"code": "EUR", "mid": 4.5}]}]).encode()
        with self.assertRaisesRegex(ValueError, "out of range"):
            capture_chunked("2026-09-01", "2026-09-30", fetch=fetch,
                            clock=lambda: datetime(2026, 11, 1, tzinfo=timezone.utc),
                            chunk_days=10)
