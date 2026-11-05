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
 close_price numeric NOT NULL
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
('USDPLN_NBP','PLN'),('GOLD_NBP_PLN_G','PLN'),
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
        self.assertEqual({r[10] for r in rows}, {"NEW_RESEARCH_RUN"})
        self.assertEqual({r[11] for r in rows}, {3})
        self.assertEqual({r[12] for r in rows}, {3})
        self.assertEqual({r[13] for r in rows}, {3})
        self.assertEqual({r[14] for r in rows}, {0})
        self.assertEqual({r[15] for r in rows}, {0})
        self.assertEqual({r[6] for r in rows}, {2})  # future ingest excluded
        self.assertEqual({str(r[7]) for r in rows}, {"100"})
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
        self.assertEqual({r[10] for r in repeated}, {"IDEMPOTENT_REPLAY"})
        self.assertEqual({r[11] for r in repeated}, {0})
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

    def test_modified_historical_evidence_fails_replay_closed(self):
        self.assertEqual({r[10] for r in self.cycle()}, {"NEW_RESEARCH_RUN"})
        # Only in this disposable fixture: model a changed historical source.
        self.conn.execute("""UPDATE investment_lab.price_observations
          SET close_price=close_price+1 WHERE instrument_code='USDPLN_NBP'""")
        collision = self.cycle()
        self.assertEqual({r[10] for r in collision}, {"REPLAY_INPUT_COLLISION"})
        self.assertEqual({r[11] for r in collision}, {0})
        self.assertEqual({r[12] for r in collision}, {0})
        self.assertEqual({r[13] for r in collision}, {0})
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.research_runs"), 3)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM investment_lab.paper_events"), 3)


if __name__ == "__main__":
    unittest.main()
