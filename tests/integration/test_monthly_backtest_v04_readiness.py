"""Disposable PostgreSQL acceptance of read-only v0.4 data readiness.

Test fixtures create and remove only their own schema after a strict
localhost + dedicated database + dedicated role verification. An existing
schema is never deleted on setup. Never point this test at Neon.
"""
from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import unittest


DISPOSABLE_DB = "isl_v04_disposable"
DISPOSABLE_USER = "isl_v04_ci"


def verify_disposable_connection(*, host, dbname, user):
    """Pure fail-closed target guard: localhost alone is insufficient."""
    if (host not in ("localhost", "127.0.0.1", "::1")
            or dbname != DISPOSABLE_DB or user != DISPOSABLE_USER):
        raise ValueError("expected dedicated localhost v0.4 disposable CI DB and role")


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
        self._owns_schema = False
        try:
            verify_disposable_connection(
                host=self.conn.info.host,
                dbname=self.conn.info.dbname,
                user=self.conn.info.user,
            )
            # The test must never erase a pre-existing schema, even in the
            # designated disposable DB (for example after a prior crash).
            exists = self.conn.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = %s)",
                ("investment_lab",),
            ).fetchone()[0]
            if exists:
                raise ValueError("pre-existing investment_lab schema: refuse reset")
            self.conn.execute("CREATE SCHEMA investment_lab")
            self._owns_schema = True
        except BaseException:
            self.conn.close()
            raise
        self.conn.execute("""CREATE TABLE investment_lab.instruments(
          instrument_code text PRIMARY KEY,
          quote_currency text NOT NULL)""")
        self.conn.execute("""CREATE TABLE investment_lab.price_observations(
          instrument_code text NOT NULL,source_code text NOT NULL,
          observed_for timestamptz NOT NULL,
          ingested_at timestamptz NOT NULL DEFAULT now(),
          interval_code text NOT NULL,
          return_basis text NOT NULL,close_price numeric NOT NULL,
          source_url text)""")

    def tearDown(self):
        try:
            if self._owns_schema:
                # Only the schema created by this test is eligible for cleanup.
                self.conn.execute("DROP SCHEMA investment_lab CASCADE")
        finally:
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
                year = 2023 + i // 12
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
        self.assertEqual({r[3] for r in rows.values()}, {0})
        self.assertEqual({r[4] for r in rows.values()}, {0})
        self.assertEqual({r[9:] for r in rows.values()}, {(0, 0)})

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

    def test_future_retrieval_not_counted_as_historical_evidence(self):
        self._insert(months=36)
        self.conn.execute("""UPDATE investment_lab.price_observations
          SET ingested_at=now()+interval '1 day'
          WHERE instrument_code='GLOBAL_EQUITY_TR_PLN'""")
        rows = self._query()
        self.assertEqual(rows["GLOBAL_EQUITY_TR_PLN"][7],
                         "NOT_RUN_SERIES_MISSING")
        self.assertEqual(rows["PL_BONDS_TR_PLN"][4], 36)
        self.assertEqual(rows["GOLD_TR_PLN"][4], 36)

    def test_36_observations_with_one_missing_month_are_not_complete(self):
        self._insert(months=37)
        self.conn.execute("""DELETE FROM investment_lab.price_observations
          WHERE EXTRACT(YEAR FROM observed_for AT TIME ZONE 'UTC')=2024
            AND EXTRACT(MONTH FROM observed_for AT TIME ZONE 'UTC')=6""")
        rows = self._query()
        self.assertEqual({r[4] for r in rows.values()}, {36})
        self.assertEqual({r[7] for r in rows.values()},
                         {"NOT_RUN_GAPPED_MONTHS"})

    def test_even_complete_index_not_marked_tradable(self):
        self._insert(months=36)
        first = self._query()
        self.assertEqual({r[7] for r in first.values()},
                         {"NEEDS_VINTAGE_AND_EXECUTION_EVIDENCE"})
        self.assertEqual({r[4] for r in first.values()}, {36})
        self.assertEqual({r[2] for r in first.values()}, {True})
        self.assertTrue(all("NEVER_INTERPRET_REFERENCE_INDEX" in r[8]
                            for r in first.values()))
        self.assertEqual(self._query(), first)
        self.assertEqual(
            self.conn.execute("""SELECT count(*) FROM
                investment_lab.price_observations""").fetchone()[0], 108)


class DisposableDatabaseGuardTests(unittest.TestCase):
    def test_rejects_local_tunnel_to_real_investment_lab_database(self):
        with self.assertRaisesRegex(ValueError, "dedicated localhost"):
            verify_disposable_connection(
                host="localhost", dbname="investment_lab", user="postgres")

    def test_rejects_remote_database_even_with_expected_name_and_role(self):
        with self.assertRaisesRegex(ValueError, "dedicated localhost"):
            verify_disposable_connection(
                host="db.example.org", dbname=DISPOSABLE_DB, user=DISPOSABLE_USER)

    def test_rejects_wrong_user_even_on_dedicated_db(self):
        with self.assertRaisesRegex(ValueError, "dedicated localhost"):
            verify_disposable_connection(
                host="127.0.0.1", dbname=DISPOSABLE_DB, user="postgres")

    def test_accepts_exact_disposable_target(self):
        self.assertIsNone(verify_disposable_connection(
            host="localhost", dbname=DISPOSABLE_DB, user=DISPOSABLE_USER))



if __name__ == "__main__":
    unittest.main()
