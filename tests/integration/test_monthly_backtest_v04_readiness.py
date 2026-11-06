"""Disposable PostgreSQL acceptance of read-only v0.4 data readiness.

Test database schema is destructively reset ONLY after the strict localhost
host check. Never run this test against Neon or any real investment datastore.
"""
from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import unittest


READINESS_SQL = (
    Path(__file__).resolve().parents[2]
    / "db/monthly_backtest_v04_readiness_READONLY.sql"
).read_text(encoding="utf-8")


@unittest.skipUnless(os.environ.get("ISL_TEST_POSTGRES_DSN"),
                     "Disposable local PostgreSQL DSN not set")
class MonthlyBacktestReadinessTest(unittest.TestCase):
    def setUp(self):
        import psycopg

        self.conn = psycopg.connect(os.environ["ISL_TEST_POSTGRES_DSN"],
                                    autocommit=True)
        if self.conn.info.host not in ("localhost", "127.0.0.1", "::1"):
            self.conn.close()
            raise ValueError("Fixture requires disposable localhost PostgreSQL")
        self.conn.execute("DROP SCHEMA IF EXISTS investment_lab CASCADE")
        self.conn.execute("CREATE SCHEMA investment_lab")
        self.conn.execute("""CREATE TABLE investment_lab.instruments(
          instrument_code text PRIMARY KEY,
          quote_currency text NOT NULL)""")
        self.conn.execute("""CREATE TABLE investment_lab.price_observations(
          instrument_code text NOT NULL,source_code text NOT NULL,
          observed_for timestamptz NOT NULL,interval_code text NOT NULL,
          return_basis text NOT NULL,close_price numeric NOT NULL,
          source_url text)""")

    def tearDown(self):
        self.conn.close()

    def _query(self):
        return {r[0]: r for r in self.conn.execute(READINESS_SQL).fetchall()}

    def _insert(self, months=12, *, basis="TOTAL_RETURN",
                currency="PLN", interval="1mo"):
        for asset in ("GLOBAL_EQUITY_TR_PLN", "PL_BONDS_TR_PLN",
                      "GOLD_TR_PLN"):
            self.conn.execute(
                "INSERT INTO investment_lab.instruments VALUES (%s,%s)",
                (asset, currency))
            for i in range(months):
                year = 2024 + i // 12
                month = i % 12 + 1
                day = date(year, month, 28)
                self.conn.execute("""INSERT INTO
                  investment_lab.price_observations
                   (instrument_code,source_code,observed_for,interval_code,
                    return_basis,close_price,source_url)
                  VALUES (%s,'fixture_research',%s,%s,%s,%s,
                    'https://research.example.org/total-return')""",
                    (asset, day.isoformat(), interval, basis, i + 100))

    def test_empty_live_equivalent_is_not_run(self):
        rows = self._query()
        self.assertEqual(len(rows), 3)
        self.assertEqual({r[7] for r in rows.values()}, {"NOT_RUN_SERIES_MISSING"})
        self.assertEqual({r[3] for r in rows}, {0})
        self.assertEqual({r[4] for r in rows}, {0})
        self.assertEqual({r[9:] for r in rows}, {(0, 0)})

    def test_price_only_and_wrong_currency_are_not_eligible(self):
        self._insert(basis="PRICE_ONLY")
        self.assertEqual({r[7] for r in self._query().values()},
                         {"NOT_RUN_SERIES_MISSING"})
        self.conn.execute("TRUNCATE investment_lab.price_observations")
        self.conn.execute("UPDATE investment_lab.instruments SET quote_currency='USD'")
        for asset in ("GLOBAL_EQUITY_TR_PLN","PL_BONDS_TR_PLN","GOLD_TR_PLN"):
            self.conn.execute("""INSERT INTO investment_lab.price_observations
              (instrument_code,source_code,observed_for,interval_code,
               return_basis,close_price,source_url)
              VALUES (%s,'fixture','2024-03-28','1mo','TOTAL_RETURN',100,
                      'https://research.example.org/total-return')""",(asset,))
        self.assertEqual({r[7] for r in self._query().values()},
                         {"NOT_RUN_SERIES_MISSING"})

    def test_short_coverage_blocks_backtest(self):
        self._insert(months=9)
        rows = self._query()
        self.assertEqual({r[7] for r in rows.values()},
                         {"NOT_RUN_INSUFFICIENT_MONTHS"})
        self.assertEqual({r[4] for r in rows.values()}, {9})

    def test_even_complete_index_not_marked_tradable(self):
        self._insert(months=12)
        first = self._query()
        self.assertEqual({r[7] for r in first.values()},
                         {"NEEDS_VINTAGE_AND_EXECUTION_EVIDENCE"})
        self.assertEqual({r[4] for r in first.values()}, {12})
        self.assertEqual({r[2] for r in first.values()}, {True})
        self.assertTrue(all("NEVER_INTERPRET_REFERENCE_INDEX" in r[8]
                            for r in first.values()))
        self.assertEqual(self._query(), first)
        self.assertEqual(
            self.conn.execute("""SELECT count(*) FROM
                investment_lab.price_observations""").fetchone()[0], 36)


if __name__ == "__main__":
    unittest.main()
