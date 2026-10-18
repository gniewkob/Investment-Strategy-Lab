"""Ephemeral PostgreSQL integration smoke test — SYNTHETIC prices only.

Runs against a disposable CI PostgreSQL service with non-production local
credentials, never against Neon or any live trading system.
"""
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
import unittest

import psycopg

from src.isl_v2.eia_sources import parse_snapshot
from src.isl_v2.eia_ingest import store
from test_eia_sources import fixture


ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("ISL_TEST_POSTGRES_URL")


@unittest.skipUnless(DSN, "Only run with disposable CI PostgreSQL service")
class EIAStagingSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = psycopg.connect(DSN, autocommit=False)
        with cls.conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS investment_lab")
            cur.execute("""CREATE TABLE IF NOT EXISTS investment_lab.data_sources(
                source_code text PRIMARY KEY)""")
            cur.execute("""CREATE TABLE IF NOT EXISTS investment_lab.instruments(
                instrument_code text PRIMARY KEY)""")
            # Apply the actual additive migration, not a handwritten replica.
            cur.execute((ROOT / "db/migrations/007_data_provenance.sql").read_text(),
                        prepare=False)
            cur.execute("INSERT INTO investment_lab.data_sources(source_code) VALUES ('eia_brent_daily') ON CONFLICT DO NOTHING")
            cur.execute("INSERT INTO investment_lab.instruments(instrument_code) VALUES ('BRENT_EIA_USD_BBL') ON CONFLICT DO NOTHING")
        cls.conn.commit()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_import_retry_revision_and_historical_visibility(self):
        captured_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        first = parse_snapshot("brent", fixture(), captured_at)
        with self.conn.cursor() as cur:
            new = store(cur, first)
            self.assertEqual(new["new"], 18)
            self.assertEqual(new["revised"], 0)
        self.conn.commit()

        with self.conn.cursor() as cur:
            dup = store(cur, first)
            self.assertTrue(dup["duplicate_run"])
            self.assertEqual(dup["new"], 0)
        self.conn.commit()

        corrected = parse_snapshot("brent", fixture(replace_cell=(0, 0, "100.95")), captured_at)
        with self.conn.cursor() as cur:
            revised = store(cur, corrected)
            self.assertEqual(revised["new"], 1)
            self.assertEqual(revised["revised"], 1)
        self.conn.commit()

        with self.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM investment_lab.source_documents")
            self.assertEqual(cur.fetchone()[0], 2)
            cur.execute("SELECT count(*) FROM investment_lab.pipeline_runs")
            self.assertEqual(cur.fetchone()[0], 2)
            cur.execute("SELECT count(*),count(*) FILTER (WHERE revision_no=2) FROM investment_lab.price_observation_versions")
            self.assertEqual(cur.fetchone(), (19, 1))
            cur.execute("SELECT count(*) FROM investment_lab.prices_asof(%s)", (datetime(2026, 10, 16, tzinfo=timezone.utc),))
            self.assertEqual(cur.fetchone()[0], 0)
            cur.execute("SELECT count(*) FROM investment_lab.prices_asof(%s)", (datetime.now(timezone.utc) + timedelta(minutes=1),))
            self.assertEqual(cur.fetchone()[0], 18)


if __name__ == "__main__":
    unittest.main()
