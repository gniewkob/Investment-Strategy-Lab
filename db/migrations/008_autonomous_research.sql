-- Sprint 2 / Investment Strategy Lab 2.0: autonomous RESEARCH and PAPER-only journal.
-- Apply only after 007_data_provenance.sql has passed production review.
-- Additive migration; no transfers, orders, brokerage or trading privileges.
CREATE TABLE IF NOT EXISTS investment_lab.agent_cycles (
 run_key text PRIMARY KEY CHECK(length(run_key) BETWEEN 8 AND 180),
 as_of timestamptz NOT NULL,
 input_sha256 text NOT NULL CHECK(input_sha256 ~ '^[a-f0-9]{64}$'),
 code_version text NOT NULL,
 completed_at timestamptz NOT NULL DEFAULT now(),
 status text NOT NULL DEFAULT 'COMPLETED_RESEARCH_ONLY'
 CHECK(status IN ('COMPLETED_RESEARCH_ONLY','INSUFFICIENT_DATA')),
 records_seen integer NOT NULL CHECK(records_seen >= 0),
 paper_fills integer NOT NULL DEFAULT 0 CHECK(paper_fills = 0),
 real_orders integer NOT NULL DEFAULT 0 CHECK(real_orders = 0),
 summary jsonb NOT NULL DEFAULT '{}'::jsonb CHECK(jsonb_typeof(summary)='object'),
 CHECK(as_of <= completed_at)
);
CREATE TABLE IF NOT EXISTS investment_lab.agent_paper_decisions (
 decision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 run_key text NOT NULL REFERENCES investment_lab.agent_cycles(run_key),
 model_code text NOT NULL REFERENCES investment_lab.models(model_code),
 signal_cutoff timestamptz NOT NULL,
 decision_type text NOT NULL CHECK(decision_type IN ('HOLD_CASH','PAPER_TARGET_INTENT')),
 target_weights jsonb NOT NULL CHECK(jsonb_typeof(target_weights)='object'),
 missing_data jsonb NOT NULL CHECK(jsonb_typeof(missing_data)='array'),
 explanation text NOT NULL,
 paper_only boolean NOT NULL DEFAULT true CHECK(paper_only=true),
 recorded_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(run_key,model_code),
 CHECK(signal_cutoff <= recorded_at)
);
CREATE TABLE IF NOT EXISTS investment_lab.agent_hypotheses (
 hypothesis_key text PRIMARY KEY CHECK(hypothesis_key ~ '^[a-f0-9]{64}$'),
 originating_run text NOT NULL REFERENCES investment_lab.agent_cycles(run_key),
 instrument_code text NOT NULL REFERENCES investment_lab.instruments(instrument_code),
 generated_as_of timestamptz NOT NULL,
 observation_date timestamptz NOT NULL,
 reference_value numeric(34,12) NOT NULL CHECK(reference_value > 0),
 predicted_direction text NOT NULL CHECK(predicted_direction IN ('UP','NON_UP')),
 statement text NOT NULL,
 falsification text NOT NULL,
 evidence_fingerprint text NOT NULL CHECK(evidence_fingerprint ~ '^[a-f0-9]{64}$'),
 research_only boolean NOT NULL DEFAULT true CHECK(research_only=true),
 recorded_at timestamptz NOT NULL DEFAULT now(),
 CHECK(observation_date <= generated_as_of),
 CHECK(generated_as_of <= recorded_at)
);
CREATE INDEX IF NOT EXISTS agent_hypotheses_instrument_idx ON investment_lab.agent_hypotheses(instrument_code,generated_as_of);
CREATE TABLE IF NOT EXISTS investment_lab.agent_hypothesis_evaluations (
 hypothesis_key text PRIMARY KEY REFERENCES investment_lab.agent_hypotheses(hypothesis_key),
 evaluated_as_of timestamptz NOT NULL,
 actual_observed_for timestamptz NOT NULL,
 actual_value numeric(34,12) NOT NULL CHECK(actual_value > 0),
 direction_correct boolean NOT NULL,
 comparator text NOT NULL DEFAULT 'PERSISTENCE_SIGN_TEST_ONLY',
 evaluation_note text NOT NULL,
 evaluated_at timestamptz NOT NULL DEFAULT now(),
 CHECK(actual_observed_for<=evaluated_as_of),
 CHECK(evaluated_as_of<=evaluated_at)
);
