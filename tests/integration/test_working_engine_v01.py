"""Disposable PostgreSQL acceptance for the REAL SQL engine; never uses Neon.

Set ISL_TEST_POSTGRES_DSN to an isolated disposable database. The test drops
the investment_lab schema; CI provisions a fresh PostgreSQL service database.
"""
from __future__ import annotations

import os
from pathlib import Path
import unittest


ENGINE_SQL = (Path(__file__).resolve().parents[2] /
              "db/working_engine_v01_research_cycle.sql").read_text(encoding="utf-8")

HEALTH_SQL = (Path(__file__).resolve().parents[2] /
              "db/working_engine_v01_health_READONLY.sql").read_text(encoding="utf-8")

V02_SQL = (Path(__file__).resolve().parents[2] /
           "db/working_engine_v02_research_cycle.sql").read_text(encoding="utf-8")

V03_SQL = (Path(__file__).resolve().parents[2] /
           "db/working_engine_v03_research_cycle.sql").read_text(encoding="utf-8")

V03_HEALTH_SQL = (Path(__file__).resolve().parents[2] /
                  "db/working_engine_v03_health_READONLY.sql").read_text(encoding="utf-8")

V02_HEALTH_SQL = (Path(__file__).resolve().parents[2] /
                  "db/working_engine_v02_health_READONLY.sql").read_text(encoding="utf-8")

NBP_METRICS_SQL = (Path(__file__).resolve().parents[2] /
                   "db/nbp_reference_metrics_v01_READONLY.sql").read_text(encoding="utf-8")

FIXTURE = """
CREATE TABLE investment_lab.models (
 model_code text PRIMARY KEY, base_currency text NOT NULL,
 simulation_only boolean NOT NULL
);
CREATE TABLE investment_lab.model_versions (
 model_code text NOT NULL, version_no integer NOT NULL, rules jsonb NOT NULL,
 PRIMARY KEY (model_code,version_no)
);
CREATE TABLE investment_lab.instruments (
 instrument_code text PRIMARY KEY, quote_currency text NOT NULL
);
CREATE TABLE investment_lab.price_observations (
 instrument_code text NOT NULL, source_code text NOT NULL,
 observed_for timestamptz NOT NULL, ingested_at timestamptz NOT NULL,
 interval_code text NOT NULL, return_basis text NOT NULL,
 close_price numeric NOT NULL, source_url text
);
CREATE TABLE investment_lab.paper_events (
 event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 model_code text NOT NULL, event_time timestamptz NOT NULL,
 recorded_at timestamptz NOT NULL, event_kind text NOT NULL,
 gross_amount numeric, fee_amount numeric NOT NULL
);
CREATE TABLE investment_lab.research_runs (
 run_id uuid PRIMARY KEY, model_code text NOT NULL, version_no integer NOT NULL,
 evaluated_at timestamptz NOT NULL, input_cutoff timestamptz NOT NULL,
 status text NOT NULL, data_sources jsonb NOT NULL, assumptions jsonb NOT NULL,
 metrics jsonb NOT NULL, findings text NOT NULL, reproducibility_hash text
);
CREATE TABLE investment_lab.signal_events (
 signal_id uuid PRIMARY KEY, model_code text NOT NULL, version_no integer NOT NULL,
 generated_at timestamptz NOT NULL, data_cutoff timestamptz NOT NULL,
 verdict text NOT NULL, evidence_score numeric, components jsonb,
 explanation text NOT NULL, invalidation_condition text, source_summary text NOT NULL
);
CREATE TABLE investment_lab.audit_events (
 audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 kind text NOT NULL, record_id text NOT NULL,
 message text NOT NULL, metadata jsonb NOT NULL
);
INSERT INTO investment_lab.models
(model_code,base_currency,simulation_only) VALUES
('M1_GLOBAL_EQ','PLN',true),('M2_DIVERSIFIED','PLN',true),
('M3_TACTICAL','PLN',true);
INSERT INTO investment_lab.model_versions
(model_code,version_no,rules) VALUES
('M1_GLOBAL_EQ',1,'{"execution":"PAPER_ONLY"}'),
('M2_DIVERSIFIED',1,'{"execution":"PAPER_ONLY"}'),
('M3_TACTICAL',1,'{"execution":"PAPER_ONLY"}');
INSERT INTO investment_lab.instruments
(instrument_code,quote_currency) VALUES
('USDPLN_NBP','PLN'),('EURPLN_NBP','PLN'),('GOLD_NBP_PLN_G','PLN'),
('GLOBAL_EQUITY_TR_PLN','PLN');
INSERT INTO investment_lab.price_observations
(instrument_code,source_code,observed_for,ingested_at,
 interval_code,return_basis,close_price) VALUES
('USDPLN_NBP','nbp',now()-interval '3 days',
 now()-interval '2 days','1d','FX_RATE',3.80),
('GOLD_NBP_PLN_G','nbp',now()-interval '3 days',
 now()-interval '2 days','1d','PRICE_ONLY',510.00),
-- A *future ingested* total-return value must not leak into the cycle.
('GLOBAL_EQUITY_TR_PLN','test_future',now()-interval '3 days',
 now()+interval '1 day','1mo','TOTAL_RETURN',100.00);
INSERT INTO investment_lab.paper_events
(model_code,event_time,recorded_at,event_kind,gross_amount,fee_amount)
VALUES
('M1_GLOBAL_EQ',now()-interval '30 days',now()-interval '29 days',
 'VIRTUAL_CONTRIBUTION',100,0),
('M2_DIVERSIFIED',now()-interval '30 days',now()-interval '29 days',
 'VIRTUAL_CONTRIBUTION',100,0),
('M3_TACTICAL',now()-interval '30 days',now()-interval '29 days',
 'VIRTUAL_CONTRIBUTION',100,0);
"""


@unittest.skipUnless(os.environ.get("ISL_TEST_POSTGRES_DSN"),
                     "Disposable PostgreSQL URL not set")
class WorkingEngineAcceptance(unittest.TestCase):
    def setUp(self):
        import psycopg

        self.conn = psycopg.connect(os.environ["ISL_TEST_POSTGRES_DSN"],
                                    autocommit=True)
        # Explicit guard: never point a destructive fixture at a real Neon host.
        info = self.conn.info
        if info.host not in ("localhost", "127.0.0.1", "::1"):
            self.conn.close()
            raise ValueError("Disposable integration tests require localhost")
        self.conn.execute("DROP SCHEMA IF EXISTS investment_lab CASCADE")
        self.conn.execute("CREATE SCHEMA investment_lab")
        self.conn.execute(FIXTURE)

    def tearDown(self):
        self.conn.close()

    def cycle(self):
        return self.conn.execute(ENGINE_SQL).fetchall()

    def scalar(self, query):
        return self.conn.execute(query).fetchone()[0]

    def test_e2e_first_run_and_idempotent_replay(self):
        rows = self.cycle()
        self.assertEqual(len(rows), 3)
        # Output order is part of the cycle contract.
        self.assertEqual([r[0] for r in rows],
                         ["M1_GLOBAL_EQ", "M2_DIVERSIFIED", "M3_TACTICAL"])
        self.assertEqual({r[11] for r in rows}, {"NEW_RESEARCH_RUN"})
        self.assertEqual({r[14] for r in rows}, {3})
        self.assertEqual({r[12] for r in rows}, {3})
        self.assertEqual({r[13] for r in rows}, {3})
        self.assertEqual({r[16] for r in rows}, {0})
        self.assertEqual({r[15] for r in rows}, {0})
        self.assertEqual({r[7] for r in rows}, {2})  # future ingest excluded
        self.assertEqual({str(r[8]) for r in rows}, {"100"})
        self.assertEqual({r[5] for r in rows}, {"INSUFFICIENT_DATA"})
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.research_runs"), 3)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.signal_events"), 3)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.audit_events"), 3)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)

        repeated = self.cycle()
        self.assertEqual(len(repeated), 3)
        self.assertEqual({r[11] for r in repeated}, {"IDEMPOTENT_REPLAY"})
        self.assertEqual({r[14] for r in repeated}, {0})
        self.assertEqual({r[12] for r in repeated}, {0})
        self.assertEqual({r[13] for r in repeated}, {0})
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.research_runs"), 3)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.audit_events"), 3)
        self.assertEqual(self.scalar(
            """SELECT count(*) FROM investment_lab.research_runs r
               JOIN investment_lab.signal_events s
                 ON s.components->>'run_id'=r.run_id::text
               JOIN investment_lab.audit_events a
                 ON a.record_id=r.run_id::text
               WHERE r.reproducibility_hash=s.components->>'input_sha256'
                 AND r.reproducibility_hash=a.metadata->>'input_sha256'"""), 3)

    def test_health_receipt_missing_before_cycle(self):
        rows = self.conn.execute(HEALTH_SQL).fetchall()
        self.assertEqual(len(rows), 3)
        self.assertEqual({r[8] for r in rows}, {"CYCLE_MISSING"})
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.research_runs"), 0)

    def test_health_receipt_consistent_after_cycle(self):
        self.cycle()
        rows = self.conn.execute(HEALTH_SQL).fetchall()
        self.assertEqual(len(rows), 3)
        self.assertEqual({r[8] for r in rows}, {"ENGINE_OK"})
        # Fixture intentionally lacks EUR/PLN: source availability is a
        # separate signal and never incorrectly changes engine execution state.
        self.assertEqual({r[9] for r in rows}, {"SOURCE_MISSING"})
        self.assertEqual({r[6] for r in rows}, {1})  # signal_rows
        self.assertEqual({r[7] for r in rows}, {1})  # audit_rows
        self.assertEqual({r[14] for r in rows}, {3})  # contribution events
        self.assertEqual({r[15] for r in rows}, {0})  # paper fills

    def test_health_receipt_detects_modified_audit(self):
        self.cycle()
        self.conn.execute("""UPDATE investment_lab.audit_events
          SET metadata=jsonb_set(metadata,'{input_sha256}','"tampered"')
          WHERE metadata->>'model_code'='M1_GLOBAL_EQ'""")
        rows = self.conn.execute(HEALTH_SQL).fetchall()
        status = {r[0]: r[8] for r in rows}
        self.assertEqual(status["M1_GLOBAL_EQ"], "CYCLE_INVALID")
        self.assertEqual(status["M2_DIVERSIFIED"], "ENGINE_OK")
        self.assertEqual(status["M3_TACTICAL"], "ENGINE_OK")
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.research_runs"), 3)

    def test_nbp_import_is_idempotent_and_detects_price_collision(self):
        import json
        from datetime import datetime, timezone
        from scripts.nbp_lab_prepare import prepare
        from scripts.nbp_lab_ingest_sql import build_sql

        fx = [{"table": "A", "no": "202/A/NBP/2026",
               "effectiveDate": "2026-11-02", "rates": [
                   {"code": "USD", "mid": 3.9123},
                   {"code": "EUR", "mid": 4.3088}]}]
        gold = [{"data": "2026-11-02", "cena": 500.43}]

        def fetch(url):
            return json.dumps(gold if "/cenyzlota/" in url else fx).encode()

        receipt = prepare("2026-11-01", "2026-11-05", fetch=fetch,
                          clock=lambda: datetime(2026, 11, 5, 21,
                                                 tzinfo=timezone.utc))
        sql = build_sql(receipt)
        # Match the real Neon primary key, only in disposable test database.
        self.conn.execute("""CREATE UNIQUE INDEX nbp_reference_fixture_pk
          ON investment_lab.price_observations
            (instrument_code,source_code,observed_for,interval_code)""")
        first = self.conn.execute(sql).fetchone()
        self.assertEqual(tuple(first), (3, 0, 3, 1, 0, 0))
        repeated = self.conn.execute(sql).fetchone()
        self.assertEqual(tuple(repeated), (3, 0, 0, 0, 0, 0))
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.audit_events"), 1)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)
        # Fixture-only tampering: original input must NEVER silently overwrite.
        self.conn.execute("""UPDATE investment_lab.price_observations
          SET close_price=999 WHERE instrument_code='USDPLN_NBP'
          AND observed_for='2026-11-02'::timestamptz""")
        conflicting = self.conn.execute(sql).fetchone()
        self.assertEqual(tuple(conflicting), (3, 1, 0, 0, 0, 0))
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.audit_events"), 1)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)

    def test_v02_seals_non_latest_historical_price_and_detects_collision(self):
        # Price ingested before cutoff but not the latest USDPLN observation.
        # v0.1 hashes only latest per instrument and total row count:
        # therefore v0.1 misses this mutation, while v0.2 must detect it.
        self.conn.execute("""INSERT INTO investment_lab.price_observations
           (instrument_code,source_code,observed_for,ingested_at,
            interval_code,return_basis,close_price)
           VALUES ('USDPLN_NBP','nbp_old',now()-interval '9 days',
             now()-interval '8 days','1d','FX_RATE',3.70)""")
        self.cycle()
        first_v2 = self.conn.execute(V02_SQL).fetchall()
        self.assertEqual({r[11] for r in first_v2}, {"NEW_RESEARCH_RUN"})
        self.assertEqual({len(r[17]) for r in first_v2}, {64})
        self.assertEqual({r[17] for r in first_v2}, {first_v2[0][17]})
        self.conn.execute("""UPDATE investment_lab.price_observations
             SET close_price=3.71 WHERE source_code='nbp_old'""")
        self.assertEqual({r[11] for r in self.cycle()}, {"IDEMPOTENT_REPLAY"})
        collision = self.conn.execute(V02_SQL).fetchall()
        self.assertEqual({r[11] for r in collision}, {"REPLAY_INPUT_COLLISION"})
        self.assertEqual({r[12] for r in collision}, {0})
        self.assertEqual({r[13] for r in collision}, {0})
        self.assertEqual({r[14] for r in collision}, {0})
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.research_runs"), 6)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)

    def test_v02_same_cutoff_uses_independent_immutable_identity(self):
        old_rows = self.cycle()
        new_rows = self.conn.execute(V02_SQL).fetchall()
        self.assertEqual({r[11] for r in new_rows}, {"NEW_RESEARCH_RUN"})
        self.assertFalse({r[3] for r in old_rows} & {r[3] for r in new_rows})
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.research_runs"), 6)
        again = self.conn.execute(V02_SQL).fetchall()
        self.assertEqual({r[11] for r in again}, {"IDEMPOTENT_REPLAY"})
        self.assertEqual({r[12] for r in again}, {0})
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.audit_events"), 6)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)

    def test_v03_readonly_health_requires_cycle_then_verifies_receipts(self):
        before = self.conn.execute(V03_HEALTH_SQL).fetchall()
        self.assertEqual({r[3] for r in before}, {"CYCLE_MISSING"})
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.research_runs"), 0)
        self.conn.execute(V03_SQL)
        health = self.conn.execute(V03_HEALTH_SQL).fetchall()
        self.assertEqual(len(health), 3)
        self.assertEqual({r[3] for r in health}, {"ENGINE_OK"})
        self.assertEqual({r[4] for r in health}, {"INSUFFICIENT_DATA"})
        self.assertEqual({r[5] for r in health},
                         {"REFERENCE_INCOMPLETE_AT_CUTOFF"})
        self.assertTrue(all(r[9] == r[10] and len(r[9]) == 64
                            for r in health))
        self.assertEqual({r[11:13] for r in health}, {(1, 1)})
        self.assertEqual({r[13:16] for r in health}, {(0, 0, 0)})
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)

    def test_v03_health_detects_mutated_old_provenance(self):
        self.conn.execute(V03_SQL)
        self.conn.execute("""UPDATE investment_lab.price_observations
          SET source_url='https://different-source.example/data'
          WHERE instrument_code='USDPLN_NBP'
            AND source_code='nbp'""")
        # In the disposable fixture, the source is explicitly 'nbp', and
        # the as-of evidence hash includes each source URL.
        changed = self.conn.execute(V03_HEALTH_SQL).fetchall()
        self.assertEqual({r[3] for r in changed},
                         {"SOURCE_OR_LEDGER_INPUT_CHANGED"})
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.research_runs"), 3)

    def test_v03_health_detects_changed_paper_event_timestamp(self):
        self.conn.execute(V03_SQL)
        self.conn.execute("""UPDATE investment_lab.paper_events
          SET event_time=event_time+interval '10 seconds'
          WHERE model_code='M1_GLOBAL_EQ'""")
        changed = self.conn.execute(V03_HEALTH_SQL).fetchall()
        status = {r[0]: r[3] for r in changed}
        self.assertEqual(status["M1_GLOBAL_EQ"],
                         "SOURCE_OR_LEDGER_INPUT_CHANGED")
        self.assertEqual(status["M2_DIVERSIFIED"], "ENGINE_OK")
        self.assertEqual(status["M3_TACTICAL"], "ENGINE_OK")

    def test_v03_persists_real_reference_context_and_ledger_in_one_cycle(self):
        receipts = self.conn.execute(V03_SQL).fetchall()
        self.assertEqual({r[11] for r in receipts}, {"NEW_RESEARCH_RUN"})
        self.assertEqual({r[18] for r in receipts},
                         {"REFERENCE_INCOMPLETE_AT_CUTOFF"})
        self.assertEqual({len(r[19]) for r in receipts}, {64})
        self.assertEqual({r[15:17] for r in receipts}, {(0, 0)})
        details = self.conn.execute("""SELECT r.model_code,r.metrics,
             r.reproducibility_hash,
             s.components,a.metadata
           FROM investment_lab.research_runs r
           JOIN investment_lab.signal_events s
              ON s.components->>'run_id'=r.run_id::text
           JOIN investment_lab.audit_events a ON a.record_id=r.run_id::text
           WHERE r.assumptions->>'engine'='working-engine-v03'
           ORDER BY r.model_code""").fetchall()
        self.assertEqual(len(details), 3)
        for model, metrics, fingerprint, signal, audit in details:
            self.assertEqual(len(metrics["nbp_reference_context"]), 3)
            self.assertEqual(len(metrics["paper_event_ledger"]), 1)
            self.assertEqual(metrics["virtual_contributions_pln"], 100)
            self.assertEqual(metrics["new_paper_events"], 0)
            self.assertEqual(metrics["real_financial_operations"], 0)
            self.assertTrue(all(reference["status_at_cutoff"]
                                == "SOURCE_MISSING_AT_CUTOFF"
                                for reference in metrics["nbp_reference_context"]))
            self.assertEqual(metrics["nbp_reference_status_at_cutoff"],
                             "REFERENCE_INCOMPLETE_AT_CUTOFF")
            self.assertEqual(signal["engine"], "working-engine-v03")
            self.assertEqual(signal["input_sha256"], fingerprint)
            self.assertEqual(audit["input_sha256"], fingerprint)
            self.assertEqual(signal["paper_event_ledger_sha256"],
                             metrics["paper_event_ledger_sha256"])
            self.assertEqual(audit["paper_event_ledger_sha256"],
                             metrics["paper_event_ledger_sha256"])
        replay = self.conn.execute(V03_SQL).fetchall()
        self.assertEqual({r[11] for r in replay}, {"IDEMPOTENT_REPLAY"})
        self.assertEqual({r[12:15] for r in replay}, {(0, 0, 0)})
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)

    def test_v03_persists_nbp_five_and_twenty_observation_metrics(self):
        self.conn.execute("""INSERT INTO investment_lab.price_observations
          (instrument_code,source_code,observed_for,ingested_at,
           interval_code,return_basis,close_price,source_url)
          SELECT 'USDPLN_NBP','nbp_rates',
                 now()-interval '27 days'+s.i*interval '1 day',
                 now()-interval '26 days'+s.i*interval '1 day',
                 '1d','FX_RATE',100+s.i,
                 'https://api.nbp.pl/api/exchangerates/tables/a/'
          FROM generate_series(0,20) s(i)""")
        self.conn.execute(V03_SQL)
        entries = self.conn.execute("""SELECT metrics->'nbp_reference_context'
          FROM investment_lab.research_runs
          WHERE assumptions->>'engine'='working-engine-v03'
          AND model_code='M1_GLOBAL_EQ'""").fetchone()[0]
        self.assertEqual(len(entries), 3)
        usd = next(x for x in entries if x["instrument_code"]=="USDPLN_NBP")
        self.assertEqual(usd["observations_in_window"], 21)
        self.assertEqual(str(usd["change_five_observations_pct"]), "4.3478")
        self.assertEqual(str(usd["change_twenty_observations_pct"]), "20.0")
        self.assertEqual(str(usd["range_twenty_observations_pct"]), "20.0")
        self.assertEqual(usd["status_at_cutoff"], "SOURCE_RECENT_AT_CUTOFF")
        self.assertEqual(usd["interpretation"],
                         "DESCRIPTIVE_REFERENCE_ONLY_NOT_TOTAL_RETURN")
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)

    def test_v03_detects_paper_ledger_change_without_budget_change(self):
        self.conn.execute(V03_SQL)
        self.conn.execute("""UPDATE investment_lab.paper_events
          SET event_time=event_time+interval '1 second'
          WHERE model_code='M1_GLOBAL_EQ'""")
        receipts = self.conn.execute(V03_SQL).fetchall()
        states = {r[0]:r[11] for r in receipts}
        self.assertEqual(states["M1_GLOBAL_EQ"], "REPLAY_INPUT_COLLISION")
        self.assertEqual(states["M2_DIVERSIFIED"], "IDEMPOTENT_REPLAY")
        self.assertEqual(states["M3_TACTICAL"], "IDEMPOTENT_REPLAY")
        self.assertEqual({r[12:15] for r in receipts}, {(0, 0, 0)})
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.research_runs"), 3)

    def test_v03_rejects_unauthorized_source_reference(self):
        self.conn.execute("""INSERT INTO investment_lab.price_observations
          (instrument_code,source_code,observed_for,ingested_at,
           interval_code,return_basis,close_price,source_url)
          VALUES ('USDPLN_NBP','nbp_rates',now()-interval '3 days',
                  now()-interval '2 days','1d','FX_RATE',900,
                  'https://not-nbp.example/api/rate')""")
        self.conn.execute(V03_SQL)
        entries = self.conn.execute("""SELECT metrics->'nbp_reference_context'
          FROM investment_lab.research_runs
          WHERE assumptions->>'engine'='working-engine-v03'
          AND model_code='M1_GLOBAL_EQ'""").fetchone()[0]
        usd = next(x for x in entries if x["instrument_code"] == "USDPLN_NBP")
        self.assertIsNone(usd["latest_value"])
        self.assertEqual(usd["status_at_cutoff"], "SOURCE_MISSING_AT_CUTOFF")
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)

    def test_v02_health_requires_v02_run_not_legacy_v01(self):
        self.cycle()
        rows = self.conn.execute(V02_HEALTH_SQL).fetchall()
        self.assertEqual({r[11] for r in rows}, {"CYCLE_MISSING"})
        self.assertEqual({r[9] for r in rows}, {0})
        self.assertEqual({r[10] for r in rows}, {0})
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.research_runs"), 3)

    def test_v02_health_matches_recomputed_market_fingerprint(self):
        self.conn.execute(V02_SQL)
        rows = self.conn.execute(V02_HEALTH_SQL).fetchall()
        self.assertEqual(len(rows), 3)
        self.assertEqual({r[11] for r in rows}, {"ENGINE_OK"})
        self.assertEqual({r[6] for r in rows}, {2})
        self.assertEqual({r[7] for r in rows}, {rows[0][7]})
        self.assertTrue(all(r[7] == r[8] and len(r[7]) == 64 for r in rows))
        self.assertEqual({r[9] for r in rows}, {1})
        self.assertEqual({r[10] for r in rows}, {1})
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)

    def test_v02_health_alerts_on_non_latest_source_mutation(self):
        self.conn.execute("""INSERT INTO investment_lab.price_observations
          (instrument_code,source_code,observed_for,ingested_at,
           interval_code,return_basis,close_price)
          VALUES ('USDPLN_NBP','nbp_backfill',now()-interval '12 days',
                   now()-interval '11 days','1d','FX_RATE',3.7)""")
        self.cycle()
        self.conn.execute(V02_SQL)
        self.conn.execute("""UPDATE investment_lab.price_observations
          SET close_price=3.75 WHERE source_code='nbp_backfill'""")
        # Legacy health only checked the saved run/signal/audit references.
        self.assertEqual({r[8] for r in self.conn.execute(HEALTH_SQL).fetchall()},
                         {"ENGINE_OK"})
        rows = self.conn.execute(V02_HEALTH_SQL).fetchall()
        self.assertEqual({r[11] for r in rows}, {"SOURCE_INPUT_CHANGED"})
        self.assertTrue(all(r[7] != r[8] for r in rows))
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)

    def test_v02_health_distinguishes_current_from_cutoff_freshness(self):
        # New references arrived after the research cutoff. They are fresh
        # TODAY, but were not available to the earlier model decision.
        self.conn.execute("""INSERT INTO investment_lab.price_observations
          (instrument_code,source_code,observed_for,ingested_at,
           interval_code,return_basis,close_price)
          VALUES
          ('USDPLN_NBP','nbp_rates',now()-interval '1 day',now(),
           '1d','FX_RATE',3.82),
          ('EURPLN_NBP','nbp_rates',now()-interval '1 day',now(),
           '1d','FX_RATE',4.32),
          ('GOLD_NBP_PLN_G','nbp_gold',now()-interval '1 day',now(),
           '1d','PRICE_ONLY',502)""")
        self.conn.execute(V02_SQL)
        rows = self.conn.execute(V02_HEALTH_SQL).fetchall()
        self.assertEqual(len(rows), 3)
        self.assertEqual({r[11] for r in rows}, {"ENGINE_OK"})
        self.assertEqual({r[12] for r in rows}, {"SOURCE_RECENT"})
        self.assertEqual({r[13] for r in rows}, {"SOURCE_MISSING_AT_CUTOFF"})
        self.assertTrue(all(r[14] is None and r[15] is None
                            and r[16] is None for r in rows))
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)

    def test_v02_health_cutoff_freshness_recovers_with_prior_ingestion(self):
        self.conn.execute("""INSERT INTO investment_lab.price_observations
          (instrument_code,source_code,observed_for,ingested_at,
           interval_code,return_basis,close_price)
          VALUES
          ('USDPLN_NBP','nbp_rates',now()-interval '3 days',
           now()-interval '2 days','1d','FX_RATE',3.82),
          ('EURPLN_NBP','nbp_rates',now()-interval '3 days',
           now()-interval '2 days','1d','FX_RATE',4.32),
          ('GOLD_NBP_PLN_G','nbp_gold',now()-interval '3 days',
           now()-interval '2 days','1d','PRICE_ONLY',502)""")
        self.conn.execute(V02_SQL)
        rows = self.conn.execute(V02_HEALTH_SQL).fetchall()
        self.assertEqual({r[11] for r in rows}, {"ENGINE_OK"})
        self.assertEqual({r[13] for r in rows}, {"SOURCE_RECENT_AT_CUTOFF"})
        self.assertTrue(all(r[14] is not None and r[15] is not None
                            and r[16] is not None for r in rows))

    def test_nbp_reference_metrics_fail_closed_when_source_missing(self):
        rows = self.conn.execute(NBP_METRICS_SQL).fetchall()
        self.assertEqual(len(rows), 3)
        self.assertEqual({r[0] for r in rows},
                         {"USDPLN_NBP", "EURPLN_NBP", "GOLD_NBP_PLN_G"})
        self.assertEqual({r[11] for r in rows}, {"SOURCE_MISSING"})
        self.assertTrue(all(r[4] == 0 and r[7] is None
                            and r[8] is None and r[9] is None
                            and r[10] is None for r in rows))
        self.assertTrue(all(r[14] == "DESCRIPTIVE_REFERENCE_ONLY_NOT_TOTAL_RETURN"
                            and r[15] == 0 and r[16] == 0 for r in rows))
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.research_runs"), 0)

    def test_nbp_reference_metrics_asof_5_and_20_observations(self):
        self.conn.execute("""INSERT INTO investment_lab.price_observations
          (instrument_code,source_code,observed_for,ingested_at,
           interval_code,return_basis,close_price,source_url)
          SELECT 'USDPLN_NBP','nbp_rates',
                 now()-interval '27 days'+s.i*interval '1 day',
                 now()-interval '26 days'+s.i*interval '1 day',
                 '1d','FX_RATE',100+s.i,
                 'https://api.nbp.pl/api/exchangerates/tables/a/'
          FROM generate_series(0,20) s(i)""")
        rows = self.conn.execute(NBP_METRICS_SQL).fetchall()
        usd = next(r for r in rows if r[0] == "USDPLN_NBP")
        self.assertEqual(usd[4], 21)
        self.assertEqual(str(usd[7]), "120")
        self.assertEqual(str(usd[8]), "4.3478")
        self.assertEqual(str(usd[9]), "20.0000")
        self.assertEqual(str(usd[10]), "20.0000")
        self.assertEqual(usd[11], "REFERENCE_RECENT")
        self.assertEqual(len(usd[13]), 64)
        # These prices are reference evidence, not tradable total returns.
        self.assertEqual(usd[2], "FX_RATE")
        self.assertEqual(usd[15:17], (0, 0))
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.research_runs"), 0)

    def test_nbp_reference_metrics_rejects_unofficial_provenance(self):
        # A numeric row with a forged source_code is not NBP evidence.
        self.conn.execute("""INSERT INTO investment_lab.price_observations
          (instrument_code,source_code,observed_for,ingested_at,
           interval_code,return_basis,close_price,source_url)
          VALUES ('USDPLN_NBP','nbp_rates',now()-interval '3 days',
                  now()-interval '2 days','1d','FX_RATE',999,
                  'https://untrusted.example/api/exchangerates/a')""")
        rows = self.conn.execute(NBP_METRICS_SQL).fetchall()
        usd = next(r for r in rows if r[0] == "USDPLN_NBP")
        self.assertEqual(usd[11], "SOURCE_MISSING")
        self.assertIsNone(usd[7])
        self.assertEqual(usd[4], 0)

    def test_nbp_reference_metrics_no_late_ingest_or_replay_lookahead(self):
        self.conn.execute("""INSERT INTO investment_lab.price_observations
          (instrument_code,source_code,observed_for,ingested_at,
           interval_code,return_basis,close_price,source_url)
          SELECT 'USDPLN_NBP','nbp_rates',
                 now()-interval '27 days'+s.i*interval '1 day',
                 now()-interval '26 days'+s.i*interval '1 day',
                 '1d','FX_RATE',100+s.i,
                 'https://api.nbp.pl/api/exchangerates/tables/a/'
          FROM generate_series(0,20) s(i)""")
        before = next(r for r in self.conn.execute(NBP_METRICS_SQL).fetchall()
                      if r[0] == "USDPLN_NBP")
        self.conn.execute("""INSERT INTO investment_lab.price_observations
          (instrument_code,source_code,observed_for,ingested_at,
           interval_code,return_basis,close_price,source_url)
          VALUES ('USDPLN_NBP','nbp_rates',now()-interval '2 days',
                  now()+interval '1 day','1d','FX_RATE',999,
                  'https://api.nbp.pl/api/exchangerates/tables/a/')""")
        after = next(r for r in self.conn.execute(NBP_METRICS_SQL).fetchall()
                     if r[0] == "USDPLN_NBP")
        self.assertEqual(before, after)
        self.conn.execute("""UPDATE investment_lab.price_observations
          SET close_price=101.5 WHERE source_code='nbp_rates'
            AND close_price=101""")
        modified = next(r for r in self.conn.execute(NBP_METRICS_SQL).fetchall()
                        if r[0] == "USDPLN_NBP")
        self.assertNotEqual(before[13], modified[13])
        self.assertEqual(before[7:11], modified[7:11])
        self.assertEqual(modified[11], "REFERENCE_RECENT")

    def test_v02_excludes_future_ingestion_even_if_revised(self):
        before = self.conn.execute(V02_SQL).fetchall()
        self.conn.execute("""UPDATE investment_lab.price_observations
          SET close_price=close_price+50
          WHERE source_code='test_future'""")
        after = self.conn.execute(V02_SQL).fetchall()
        self.assertEqual({r[11] for r in after}, {"IDEMPOTENT_REPLAY"})
        self.assertEqual({r[17] for r in before}, {r[17] for r in after})
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)

    def test_modified_historical_evidence_fails_replay_closed(self):
        self.assertEqual({r[11] for r in self.cycle()}, {"NEW_RESEARCH_RUN"})
        # Only in this disposable fixture: model a changed historical source.
        self.conn.execute("""UPDATE investment_lab.price_observations
          SET close_price=close_price+1 WHERE instrument_code='USDPLN_NBP'""")
        collision = self.cycle()
        self.assertEqual({r[11] for r in collision}, {"REPLAY_INPUT_COLLISION"})
        self.assertEqual({r[14] for r in collision}, {0})
        self.assertEqual({r[12] for r in collision}, {0})
        self.assertEqual({r[13] for r in collision}, {0})
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.research_runs"), 3)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)


    def test_v03_replay_and_health_stable_across_session_timezones(self):
        # The same UTC cutoff and source rows must never generate new UUIDs,
        # fingerprints or research rows in sessions using a different TimeZone.
        self.conn.execute("SET TIME ZONE 'UTC'")
        first = self.conn.execute(V03_SQL).fetchall()
        self.assertEqual({row[11] for row in first}, {"NEW_RESEARCH_RUN"})
        pinned = {row[0]: (row[3], row[4], row[17], row[19]) for row in first}
        self.conn.execute("SET TIME ZONE 'Europe/Warsaw'")
        replay = self.conn.execute(V03_SQL).fetchall()
        self.assertEqual({row[11] for row in replay}, {"IDEMPOTENT_REPLAY"})
        self.assertEqual({row[0]: (row[3], row[4], row[17], row[19])
                          for row in replay}, pinned)
        self.assertEqual({row[3] for row in self.conn.execute(
            V03_HEALTH_SQL).fetchall()}, {"ENGINE_OK"})
        self.conn.execute("SET TIME ZONE 'UTC'")
        self.assertEqual({row[3] for row in self.conn.execute(
            V03_HEALTH_SQL).fetchall()}, {"ENGINE_OK"})
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.research_runs"), 3)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)

    def test_v03_health_rejects_missing_required_safety_fields(self):
        self.conn.execute(V03_SQL)
        self.conn.execute("""UPDATE investment_lab.research_runs
          SET assumptions=assumptions - 'engine'
          WHERE model_code='M1_GLOBAL_EQ'
            AND assumptions->>'engine'='working-engine-v03'""")
        self.conn.execute("""UPDATE investment_lab.research_runs
          SET metrics=metrics - 'real_financial_operations'
          WHERE model_code='M2_DIVERSIFIED'
            AND assumptions->>'engine'='working-engine-v03'""")
        self.conn.execute("""UPDATE investment_lab.research_runs
          SET metrics=metrics - 'new_paper_events'
          WHERE model_code='M3_TACTICAL'
            AND assumptions->>'engine'='working-engine-v03'""")
        status = {row[0]: row[3] for row in self.conn.execute(
            V03_HEALTH_SQL).fetchall()}
        self.assertEqual(status, {
            "M1_GLOBAL_EQ": "CYCLE_INVALID",
            "M2_DIVERSIFIED": "CYCLE_INVALID",
            "M3_TACTICAL": "CYCLE_INVALID",
        })
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)

    def test_nbp_compiled_ingest_keeps_single_utc_observation_across_timezones(self):
        from scripts.nbp_lab_ingest_sql import build_sql
        from tests.test_nbp_lab_ingest_sql import receipt

        # Disposable fixture only. Real LAB schema is never mutated.
        self.conn.execute("""CREATE UNIQUE INDEX test_nbp_source_uniq
          ON investment_lab.price_observations
          (instrument_code,source_code,observed_for,interval_code)""")
        sql = build_sql(receipt())
        self.conn.execute("SET TIME ZONE 'Europe/Warsaw'")
        initial = self.conn.execute(sql).fetchone()
        self.assertEqual(initial[2], 3)
        self.conn.execute("SET TIME ZONE 'UTC'")
        replay = self.conn.execute(sql).fetchone()
        self.assertEqual(replay[1:4], (0, 0, 0))
        rows = self.conn.execute("""SELECT instrument_code,
                   (observed_for AT TIME ZONE 'UTC')::date
          FROM investment_lab.price_observations
          WHERE source_code IN ('nbp_rates','nbp_gold')
          ORDER BY instrument_code""").fetchall()
        self.assertEqual(len(rows), 3)
        self.assertEqual({str(row[1]) for row in rows}, {"2026-11-02"})
        self.assertEqual(self.scalar("""SELECT count(*)
          FROM investment_lab.audit_events WHERE kind='INGEST'"""), 1)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)


if __name__ == "__main__":
    unittest.main()
