-- REVIEW / EPHEMERAL CI ONLY: least-privilege roles for research-only pipeline.
-- Do not apply on production or provision LOGIN roles without a separate approval.
-- All roles are intentionally NOLOGIN; the SQL contains no passwords or DSNs.
-- Expected prerequisites: schema investment_lab, migrations 007 and 008, and
-- original baseline tables data_sources, instruments and models.
DO $isl_roles$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY[
    'isl_eia_ingest',
    'isl_market_reader',
    'isl_journal_append',
    'isl_agent_runtime'
  ] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
      EXECUTE format('CREATE ROLE %I NOLOGIN', role_name);
    END IF;
  END LOOP;
END
$isl_roles$;

-- Public must never inherit permissions to research materials from this file.
REVOKE ALL ON SCHEMA investment_lab FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION investment_lab.prices_asof(timestamptz) FROM PUBLIC;
REVOKE ALL ON TABLE
  investment_lab.source_documents,
  investment_lab.price_observation_versions,
  investment_lab.pipeline_runs,
  investment_lab.pipeline_run_events,
  investment_lab.agent_cycles,
  investment_lab.agent_paper_decisions,
  investment_lab.agent_hypotheses,
  investment_lab.agent_hypothesis_evaluations
FROM PUBLIC;

GRANT USAGE ON SCHEMA investment_lab TO
  isl_eia_ingest, isl_market_reader, isl_journal_append;

-- Ingestion can only read catalogues and append new sourced material.
-- No UPDATE, DELETE, TRUNCATE, CREATE, ALTER or ownership transfer.
GRANT SELECT ON investment_lab.data_sources, investment_lab.instruments
  TO isl_eia_ingest;
GRANT SELECT, INSERT ON
  investment_lab.source_documents,
  investment_lab.price_observation_versions,
  investment_lab.pipeline_runs,
  investment_lab.pipeline_run_events
  TO isl_eia_ingest;
GRANT USAGE ON SEQUENCE investment_lab.pipeline_run_events_event_id_seq TO isl_eia_ingest;

-- Agent's market-data component is strictly read only.
GRANT SELECT ON investment_lab.source_documents,
  investment_lab.price_observation_versions, investment_lab.instruments
  TO isl_market_reader;
GRANT EXECUTE ON FUNCTION investment_lab.prices_asof(timestamptz)
  TO isl_market_reader;

-- Agent may only append immutable research journal entries and read those
-- previous entries. It cannot write EIA snapshots or old paper_events.
GRANT SELECT ON investment_lab.models TO isl_journal_append;
GRANT SELECT, INSERT ON
  investment_lab.agent_cycles,
  investment_lab.agent_paper_decisions,
  investment_lab.agent_hypotheses,
  investment_lab.agent_hypothesis_evaluations
  TO isl_journal_append;

-- Runtime identity combines read-only evidence with append-only research.
GRANT isl_market_reader, isl_journal_append TO isl_agent_runtime;
