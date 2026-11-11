"""Offline safety/identity tests for public NBP ingestion receipt."""
import json
import unittest
from datetime import datetime, timezone

from scripts.nbp_lab_prepare import prepare

NOW = datetime(2026, 11, 5, 21, tzinfo=timezone.utc)
FX = [
    {"table": "A", "no": "202/A/NBP/2026", "effectiveDate": "2026-11-02",
     "rates": [{"code": "USD", "mid": 3.9123}, {"code": "EUR", "mid": 4.3088}]},
    {"table": "A", "no": "203/A/NBP/2026", "effectiveDate": "2026-11-03",
     "rates": [{"code": "USD", "mid": 3.9001}, {"code": "EUR", "mid": 4.3204}]},
]
GOLD = [{"data": "2026-11-02", "cena": 500.43},
        {"data": "2026-11-03", "cena": 501.56}]


def fixture_fetch(url):
    return json.dumps(GOLD if "/cenyzlota/" in url else FX).encode()


class NBPLabReceiptTests(unittest.TestCase):
    def run_receipt(self, fetch=fixture_fetch, clock=lambda: NOW):
        return prepare("2026-11-01", "2026-11-05", fetch=fetch, clock=clock)

    def test_identity_basis_provenance_and_no_orders(self):
        result = self.run_receipt()
        self.assertEqual(result["row_count"], 6)
        self.assertEqual(result["by_series"], {"usdpln": 2, "eurpln": 2, "gold": 2})
        rows = result["rows"]
        self.assertEqual({r["instrument_code"] for r in rows},
                         {"USDPLN_NBP", "EURPLN_NBP", "GOLD_NBP_PLN_G"})
        self.assertEqual({r["return_basis"] for r in rows},
                         {"FX_RATE", "PRICE_ONLY"})
        self.assertTrue(all(r["source_url"].startswith("https://api.nbp.pl/api/")
                            for r in rows))
        self.assertTrue(all(len(r["source_sha256"]) == 64 for r in rows))
        self.assertFalse(result["historical_source_vintage_verified"])
        self.assertFalse(result["historical_publication_hour_verified"])
        self.assertFalse(result["ingestion_authorized"])
        self.assertEqual(result["paper_events_created"], 0)
        self.assertEqual(result["real_financial_operations"], 0)

    def test_future_publication_is_rejected(self):
        def bad_fetch(url):
            data = GOLD if "/cenyzlota/" in url else FX
            copied = json.loads(json.dumps(data))
            if "/cenyzlota/" in url:
                copied[0]["data"] = "2026-11-05"
            return json.dumps(copied).encode()

        with self.assertRaisesRegex(ValueError, "future publication date"):
            self.run_receipt(fetch=bad_fetch,
                             clock=lambda: datetime(2026, 11, 4, tzinfo=timezone.utc))

    def test_missing_currency_rejects_all(self):
        def bad_fetch(url):
            return json.dumps(GOLD if "/cenyzlota/" in url else [
                {"table": "A", "no": "202/A/NBP/2026", "effectiveDate": "2026-11-02",
                 "rates": [{"code": "USD", "mid": 3.91}]}
            ]).encode()
        with self.assertRaisesRegex(ValueError, "exchange rate"):
            self.run_receipt(fetch=bad_fetch)

    def test_duplicate_dates_rejected_not_silently_overwritten(self):
        def bad_fetch(url):
            return json.dumps([GOLD[0], GOLD[0]] if "/cenyzlota/" in url else FX).encode()
        with self.assertRaisesRegex(ValueError, "duplicate publication date"):
            self.run_receipt(fetch=bad_fetch)

    def test_empty_or_unavailable_source_fails_closed(self):
        def bad_fetch(url):
            if "/cenyzlota/" in url:
                raise OSError("network failure")
            return json.dumps(FX).encode()
        with self.assertRaises(OSError):
            self.run_receipt(fetch=bad_fetch)


if __name__ == "__main__":
    unittest.main()
