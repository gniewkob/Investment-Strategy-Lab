"""Real PostgreSQL permission boundary tests, never Neon production.

Uses the disposable local CI database and NOLOGIN roles. Credentials are
synthetic CI-only and do not provide access to any hosted database.
"""
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
import unittest

import psycopg

from src.isl_v2.autonomous_agent import run_cycle
from src.isl_v2.agent_runner import store_cycle, assert_research_runtime
from src.isl_v2.eia_sources import parse_snapshot
from src.isl_v2.eia_ingest import store
from test_eia_sources import fixture

ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("ISL_TEST_POSTGRES_URL")
MODELS = ("M1_GLOBAL_EQ", "M2_DIVERSIFIED", "M3_TACTICAL")


@unittest.skipUnless(DSN, "Requires disposable PostgreSQL CI service")
class LeastPrivilegeSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with psycopg.connect(DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE SCHEMA IF NOT EXISTS investment_lab")
                for tbl,col in (("data_sources","source_code"),("instruments","instrument_code"),("models","model_code")):
                    cur.execute(f"CREATE TABLE IF NOT EXISTS investment_lab.{tbl} ({col} text PRIMARY KEY)")
                cur.execute((ROOT / "db/migrations/007_data_provenance.sql").read_text(), prepare=False)
                cur.execute((ROOT / "db/migrations/008_autonomous_research.sql").read_text(), prepare=False)
                for code in MODELS:
                    cur.execute("INSERT INTO investment_lab.models(model_code) VALUES (%s) ON CONFLICT DO NOTHING",(code,))
                cur.execute("INSERT INTO investment_lab.data_sources(source_code) VALUES ('eia_brent_daily') ON CONFLICT DO NOTHING")
                cur.execute("INSERT INTO investment_lab.instruments(instrument_code) VALUES ('BRENT_EIA_USD_BBL') ON CONFLICT DO NOTHING")
                cur.execute((ROOT / "db/security/least_privilege_roles_CI_REVIEW.sql").read_text(), prepare=False)

    def test_roles_are_nonlogin_and_have_no_ddl(self):
        with psycopg.connect(DSN) as conn, conn.cursor() as cur:
            cur.execute("""SELECT rolname,rolcanlogin,rolcreaterole,rolcreatedb,rolsuper
                          FROM pg_roles WHERE rolname=ANY(%s) ORDER BY rolname""",
                        (["isl_eia_ingest","isl_market_reader","isl_journal_append","isl_agent_runtime"],))
            roles=cur.fetchall()
            self.assertEqual(len(roles),4)
            for name, login, create_role, create_db, superuser in roles:
                self.assertFalse(login,name)
                self.assertFalse(create_role,name)
                self.assertFalse(create_db,name)
                self.assertFalse(superuser,name)
                cur.execute("SELECT has_schema_privilege(%s,'investment_lab','CREATE')",(name,))
                self.assertFalse(cur.fetchone()[0],name)

    def test_roles_cannot_modify_evidence_or_previous_research(self):
        with psycopg.connect(DSN) as conn, conn.cursor() as cur:
            for role in ("isl_agent_runtime", "isl_journal_append", "isl_market_reader"):
                for table in ("source_documents", "price_observation_versions"):
                    cur.execute("SELECT has_table_privilege(%s,%s,'INSERT,UPDATE,DELETE,TRUNCATE')",
                                (role,"investment_lab."+table))
                    self.assertFalse(cur.fetchone()[0],f"{role} writes {table}")
            for role in ("isl_eia_ingest", "isl_agent_runtime"):
                for table in ("agent_cycles","agent_paper_decisions","agent_hypotheses"):
                    for privilege in ("UPDATE","DELETE","TRUNCATE"):
                        cur.execute("SELECT has_table_privilege(%s,%s,%s)",
                                    (role,"investment_lab."+table,privilege))
                        self.assertFalse(cur.fetchone()[0],f"{role} has {privilege} on {table}")
            cur.execute("SELECT has_table_privilege('isl_eia_ingest','investment_lab.agent_cycles','INSERT')")
            self.assertFalse(cur.fetchone()[0])

    def test_runtime_append_only_idempotent_cycle(self):
        today=datetime.now(timezone.utc).replace(microsecond=0)
        result=run_cycle({"run_key":"ci-agent-least-privilege-v1",
                          "code_version":"2.0.1-security","as_of":today.isoformat(),
                          "observations":[],"requirements":{}})
        with psycopg.connect(DSN) as conn, conn.cursor() as cur:
            cur.execute("SET ROLE isl_agent_runtime")
            assert_research_runtime(cur)
            self.assertTrue(store_cycle(cur,result))
            self.assertFalse(store_cycle(cur,result))
            cur.execute("SELECT count(*) FROM investment_lab.agent_paper_decisions WHERE run_key=%s",(result["run_key"],))
            self.assertEqual(cur.fetchone()[0],3)
            self.assertTrue(all(x["decision_type"]=="HOLD_CASH" for x in result["paper_decisions"]))
            self.assertEqual(result["paper_fills_created"],0)
            self.assertEqual(result["real_orders_created"],0)

    def test_market_source_ingester_can_append_only(self):
        when=datetime.now(timezone.utc)-timedelta(seconds=30)
        snapshot=parse_snapshot("brent",fixture(replace_cell=(1,3,"120.24")),when)
        with psycopg.connect(DSN) as conn, conn.cursor() as cur:
            cur.execute("SET ROLE isl_eia_ingest")
            result=store(cur,snapshot)
            self.assertGreaterEqual(result["new"],1)
            self.assertFalse(result["duplicate_run"])
            self.assertTrue(store(cur,snapshot)["duplicate_run"])

    def test_owner_and_ingester_fail_agent_startup_guard(self):
        with psycopg.connect(DSN) as conn, conn.cursor() as cur:
            # The CI database owner must not be usable by scheduled agent.
            with self.assertRaises(RuntimeError):
                assert_research_runtime(cur)
            cur.execute("SET ROLE isl_eia_ingest")
            with self.assertRaises(RuntimeError):
                assert_research_runtime(cur)
            cur.execute("RESET ROLE")
            cur.execute("SET ROLE isl_market_reader")
            with self.assertRaises(RuntimeError):
                assert_research_runtime(cur)

    def test_roles_separation_is_real_not_just_acl_metadata(self):
        with psycopg.connect(DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SET ROLE isl_market_reader")
                cur.execute("SELECT count(*) FROM investment_lab.prices_asof(%s)",(datetime.now(timezone.utc),))
                self.assertGreaterEqual(cur.fetchone()[0],0)
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with conn.transaction():
                        cur.execute("INSERT INTO investment_lab.agent_cycles(run_key,as_of,input_sha256,code_version,records_seen) VALUES ('not-authorized',now(),repeat('a',64),'test',0)")
            conn.rollback()
        with psycopg.connect(DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SET ROLE isl_agent_runtime")
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with conn.transaction():
                        cur.execute("INSERT INTO investment_lab.pipeline_runs(run_key,pipeline_name,code_version,status) VALUES ('no-source-write','not_allowed','x','STARTED')")
            conn.rollback()


if __name__ == "__main__":
    unittest.main()
