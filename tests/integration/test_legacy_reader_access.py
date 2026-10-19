"""Ephemeral PostgreSQL ACL checks; NEVER touches Neon or real credentials."""
import os
from pathlib import Path
import unittest

try:
    import psycopg
except ImportError:
    psycopg = None

DSN = os.getenv("ISL_TEST_POSTGRES_URL")
SQL = Path(__file__).resolve().parents[2] / "db/security/legacy_history_reader_STAGING_REVIEW.sql"


@unittest.skipUnless(DSN and psycopg, "Requires disposable PostgreSQL service")
class HistoricalRoleAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with psycopg.connect(DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE SCHEMA investment_lab")
                cur.execute("""CREATE TABLE investment_lab.price_observations (
                    instrument_code text, source_code text, observed_for timestamptz,
                    ingested_at timestamptz, interval_code text, return_basis text,
                    close_price numeric
                )""")
                for table in ("holding_snapshots", "valuations", "paper_events", "agent_cycles"):
                    cur.execute(f"CREATE TABLE investment_lab.{table} (id integer)")
                cur.execute("""
                    INSERT INTO investment_lab.price_observations VALUES
                    ('BTC-USD','coinbase_spot',now(),now(),'1d','PRICE_ONLY',100)
                """)
                cur.execute(SQL.read_text(encoding="utf-8"), prepare=False)

    def test_no_login_admin_or_ddl(self):
        with psycopg.connect(DSN) as conn, conn.cursor() as cur:
            cur.execute("""SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolbypassrls
                           FROM pg_roles WHERE rolname='isl_legacy_history_reader'""")
            self.assertEqual(cur.fetchone(), (False, False, False, False, False))
            for target in ("investment_lab",):
                cur.execute("SELECT has_schema_privilege(%s,%s,'CREATE')",
                            ("isl_legacy_history_reader", target))
                self.assertFalse(cur.fetchone()[0])

    def test_reader_can_select_market_history_only(self):
        with psycopg.connect(DSN) as conn, conn.cursor() as cur:
            cur.execute("SET ROLE isl_legacy_history_reader")
            cur.execute("""SELECT instrument_code,source_code,observed_for,
                                  ingested_at,interval_code,return_basis,close_price
                           FROM investment_lab.price_observations""")
            self.assertEqual(len(cur.fetchall()), 1)
            cur.execute("SELECT current_user")
            self.assertEqual(cur.fetchone()[0], "isl_legacy_history_reader")

    def test_private_tables_remain_forbidden(self):
        for table in ("holding_snapshots", "valuations", "paper_events", "agent_cycles"):
            with self.subTest(table=table):
                with psycopg.connect(DSN) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SET ROLE isl_legacy_history_reader")
                        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                            cur.execute(f"SELECT * FROM investment_lab.{table}")

    def test_market_insert_and_schema_create_are_forbidden(self):
        for sql in (
            "INSERT INTO investment_lab.price_observations(instrument_code) VALUES ('X')",
            "CREATE TABLE investment_lab.unapproved_access (v integer)",
        ):
            with self.subTest(operation=sql.split(" ")[0]):
                with psycopg.connect(DSN) as conn, conn.cursor() as cur:
                    cur.execute("SET ROLE isl_legacy_history_reader")
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        cur.execute(sql)

    def test_fails_closed_on_repeated_role_creation(self):
        with psycopg.connect(DSN) as conn, conn.cursor() as cur:
            with self.assertRaises(psycopg.errors.RaiseException):
                cur.execute(SQL.read_text(encoding="utf-8"), prepare=False)


if __name__ == "__main__":
    unittest.main()
