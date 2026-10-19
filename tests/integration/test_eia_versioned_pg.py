"""Real PostgreSQL integration in an EPHEMERAL CI SERVICE ONLY.

Never point ISL_TEST_POSTGRES_URL at Neon, external DNS, or production.
Uses reviewed migration-007 fixture, synthetic HTML, and fake local roles.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from pathlib import Path
import unittest
from urllib.parse import urlsplit

from src.isl_v2.eia_versioned_ingest import (
    EXPECTED_DATABASE, EXPECTED_WRITER, apply_plan, prepare,
)
from src.isl_v2.eia_sources import SourceFormatError

DSN = os.environ.get("ISL_TEST_POSTGRES_URL")
ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 18, 8, 30, tzinfo=timezone.utc)


def fixture(replace_cell=None):
    base = [
        ("2026 Sep-21 to Sep-25", ["101.10","101.20","101.30","101.40","101.50"]),
        ("2026 Sep-28 to Oct- 2", ["102.10","102.20","102.30","102.40","102.50"]),
        ("2026 Oct- 5 to Oct- 9", ["103.10","103.20","103.30","103.40","103.50"]),
        ("2026 Oct-12 to Oct-16", ["104.10","104.20","104.30","",""]),
    ]
    if replace_cell is not None:
        week,day,value = replace_cell
        base[week][1][day] = value
    return ("<html><body><table>" +
            "".join("<tr><td>"+period+"</td>"+
                    "".join("<td>"+value+"</td>" for value in cells)+"</tr>"
                    for period,cells in base) +
            "</table><div>Release Date: 10/15/2026</div></body></html>").encode()


@unittest.skipUnless(DSN, "Disposable PostgreSQL CI ONLY")
class VersionedEiaPgIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parsed = urlsplit(DSN)
        # Refuse any accidental remote test DB target.
        if (parsed.hostname not in ("localhost","127.0.0.1")
                or parsed.path != "/investment_lab"):
            raise RuntimeError("Integration fixture refuses nonlocal or wrong database")
        import psycopg
        cls.conn = psycopg.connect(DSN)
        with cls.conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS investment_lab")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS investment_lab.data_sources
                  (source_code text PRIMARY KEY)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS investment_lab.instruments
                  (instrument_code text PRIMARY KEY)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS investment_lab.price_observations
                  (instrument_code text PRIMARY KEY)
            """)
            for table in ("holding_snapshots","valuations","paper_events"):
                # Only dummy ACL sentinels exist, never real private data.
                cur.execute("CREATE TABLE IF NOT EXISTS investment_lab."
                            + table + " (dummy_id integer)")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS investment_lab.agent_cycles
                (run_key text PRIMARY KEY)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS investment_lab.agent_paper_decisions
                (run_key text, decision_type text)
            """)
            migration = (
                ROOT / "tests/fixtures/eia_pit_schema_007_disposable.sql"
            ).read_text(encoding="utf-8")
            cur.execute(migration, prepare=False)
            cur.execute("""
                DO $$
                BEGIN
                  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='neon_superuser')
                  THEN CREATE ROLE neon_superuser NOLOGIN; END IF;
                END $$;
            """)
            cur.execute("""
                INSERT INTO investment_lab.agent_cycles(run_key)
                VALUES ('staging-security-canary-2026-10-18')
            """)
            cur.execute("""
                INSERT INTO investment_lab.agent_paper_decisions
                  (run_key,decision_type)
                VALUES ('staging-security-canary-2026-10-18','HOLD_CASH'),
                       ('staging-security-canary-2026-10-18','HOLD_CASH'),
                       ('staging-security-canary-2026-10-18','HOLD_CASH')
            """)
            cur.execute("""
                INSERT INTO investment_lab.data_sources(source_code)
                VALUES ('eia_wti_daily') ON CONFLICT DO NOTHING
            """)
            cur.execute("""
                INSERT INTO investment_lab.instruments(instrument_code)
                VALUES ('WTI_EIA_USD_BBL') ON CONFLICT DO NOTHING
            """)
        cls.conn.commit()
        # The REVIEW ONLY role SQL is executed ONLY against this throwaway
        # localhost PostgreSQL; production/staging Neon is never addressed.
        cls.conn.autocommit = True
        with cls.conn.cursor() as cur:
            cur.execute(
                (ROOT / "db/security/eia_pit_staging_writer_REVIEW_ONLY.sql").read_text(),
                prepare=False,
            )
        cls.conn.autocommit = False

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        with self.conn.cursor() as cur:
            cur.execute("RESET ROLE")
            cur.execute("""
                TRUNCATE investment_lab.price_observation_versions,
                         investment_lab.source_documents CASCADE
            """)
            cur.execute("""
                REVOKE SELECT ON investment_lab.holding_snapshots
                FROM isl_eia_pit_staging_writer
            """)
        self.conn.commit()
        with self.conn.cursor() as cur:
            cur.execute("SET ROLE isl_eia_pit_staging_writer")

    def tearDown(self):
        try:
            self.conn.rollback()
        finally:
            with self.conn.cursor() as cur:
                cur.execute("RESET ROLE")
            self.conn.commit()

    def test_real_tables_idempotency_correction_and_no_future_visibility(self):
        first = prepare("wti",fixture(),NOW)
        second = prepare("wti",fixture(replace_cell=(0,0,"100.95")),
                         NOW+timedelta(days=1))
        with self.conn.cursor() as cur:
            x = apply_plan(cur,first)
            self.assertEqual(x["new_observation_versions"],18)
            self.assertTrue(x["document_added"])
        self.conn.commit()

        with self.conn.cursor() as cur:
            retry = apply_plan(cur,first)
            self.assertFalse(retry["document_added"])
            self.assertEqual(retry["new_observation_versions"],0)
        self.conn.commit()

        with self.conn.cursor() as cur:
            changed = apply_plan(cur,second)
            self.assertEqual(changed["new_observation_versions"],1)
            self.assertEqual(changed["revised_observation_versions"],1)
        self.conn.commit()

        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM investment_lab.source_documents")
            self.assertEqual(cur.fetchone()[0],2)
            cur.execute("""
                SELECT COUNT(*), COUNT(*) FILTER (WHERE revision_no=2),
                       COUNT(*) FILTER (WHERE note LIKE '%NOT_ORIGINAL%')
                FROM investment_lab.price_observation_versions
            """)
            self.assertEqual(cur.fetchone(),(19,1,19))
            cur.execute("SELECT COUNT(*) FROM investment_lab.prices_asof(%s)",
                        (datetime(2026,10,16,tzinfo=timezone.utc),))
            self.assertEqual(cur.fetchone()[0],0)
            cur.execute("SELECT COUNT(*) FROM investment_lab.prices_asof(now())")
            self.assertEqual(cur.fetchone()[0],18)
            cur.execute("""
                SELECT MAX(revision_no) FROM investment_lab.prices_asof(now())
                WHERE observed_for='2026-09-21 00:00:00+00'
            """)
            self.assertEqual(cur.fetchone()[0],2)

    def test_real_acl_refuses_privileged_or_role_changed(self):
        with self.conn.cursor() as cur:
            cur.execute("RESET ROLE")
            cur.execute("""
                GRANT SELECT ON investment_lab.holding_snapshots
                TO isl_eia_pit_staging_writer
            """)
            cur.execute("SET ROLE isl_eia_pit_staging_writer")
            with self.assertRaisesRegex(SourceFormatError,"writer"):
                apply_plan(cur,prepare("wti",fixture(),NOW))
        self.conn.rollback()
        with self.conn.cursor() as cur:
            cur.execute("RESET ROLE")
            cur.execute("SET ROLE isl_eia_pit_staging_writer")
            # Even the less-privileged planned role must not be present
            # or silently created in a Neon database by the CI fixture.


if __name__ == "__main__":
    unittest.main()
