"""No-network tests of the deterministic NBP-to-Neon SQL compiler."""
import copy
import json
import unittest
from datetime import datetime, timezone

from scripts.nbp_lab_prepare import prepare
from scripts.nbp_lab_ingest_sql import build_sql

NOW = datetime(2026, 11, 5, 21, 0, tzinfo=timezone.utc)
FX = [{"table": "A", "no": "202/A/NBP/2026", "effectiveDate": "2026-11-02",
       "rates": [{"code": "USD", "mid": 3.9123}, {"code": "EUR", "mid": 4.3088}]}]
GOLD = [{"data": "2026-11-02", "cena": 500.43}]


def receipt():
    def fetch(url):
        return json.dumps(GOLD if "/cenyzlota/" in url else FX).encode()
    return prepare("2026-11-01", "2026-11-05",
                   fetch=fetch, clock=lambda: NOW)


class NBPSqlCompilationTests(unittest.TestCase):
    def test_generates_single_bounded_research_ingest(self):
        sql = build_sql(receipt())
        self.assertIn("INSERT INTO investment_lab.price_observations", sql)
        self.assertIn("INSERT INTO investment_lab.audit_events", sql)
        self.assertIn("ON CONFLICT (instrument_code,source_code,observed_for,interval_code) DO NOTHING", sql)
        self.assertNotIn("INSERT INTO investment_lab.paper_events", sql)
        self.assertNotIn("DELETE FROM", sql)
        self.assertNotIn("DROP TABLE", sql)
        self.assertIn("original_publication_hour_known',false", sql)
        self.assertEqual(sql, build_sql(receipt()))

    def test_publication_date_uses_explicit_utc_midnight(self):
        sql = build_sql(receipt())
        self.assertEqual(sql.count("(c.publication_day::timestamp AT TIME ZONE 'UTC')"), 2)
        self.assertNotIn("c.publication_day::timestamptz", sql)

    def test_rejects_tampered_price_and_source(self):
        for field, value in (("close_price", "-1"),
                             ("source_code", "coinbase_spot"),
                             ("return_basis", "TOTAL_RETURN"),
                             ("source_url", "https://evil.example/x"),
                             ("source_sha256", "0" * 64)):
            r = receipt()
            r["rows"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                build_sql(r)

    def test_rejects_fabricated_eligibility_and_financial_event(self):
        for field, value in (("historical_publication_hour_verified", True),
                             ("paper_events_created", 1),
                             ("real_financial_operations", 1),
                             ("market_data_kind", "TOTAL_RETURN")):
            r = receipt()
            r[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                build_sql(r)

    def test_duplicate_and_unbalanced_series_rejected(self):
        r = receipt()
        r["rows"].append(copy.deepcopy(r["rows"][0]))
        r["row_count"] += 1
        r["by_series"]["eurpln"] += 1
        with self.assertRaises(ValueError):
            build_sql(r)

    def test_source_retrieval_date_cannot_be_backdated(self):
        r = receipt()
        r["source_receipts"]["fx"]["retrieved_at"] = "2026-10-01T10:00:00Z"
        with self.assertRaises(ValueError):
            build_sql(r)


if __name__ == "__main__":
    unittest.main()
