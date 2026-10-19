-- REVIEW ONLY: historical reference reader for ISOLATED Neon STAGING.
-- Never run against Neon production, never run from pull_request CI.
-- The role is NOLOGIN by design until a separate authorized interactive
-- credential-provisioning step. The SQL contains NO passwords or tokens.
--
-- Existing educational research agent isl_agent_staging_limited stays unchanged.
-- This access is for the reference-only historical export in
-- scripts/legacy_history_bridge.py, NOT portfolio or brokerage data.

DO $review$
BEGIN
  -- Fail closed if anyone has already made a role with this name.
  -- In particular, do not silently reconfigure a pre-existing login.
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='isl_legacy_history_reader') THEN
    RAISE EXCEPTION 'Historical reader already exists; manual role audit required';
  END IF;
  CREATE ROLE isl_legacy_history_reader NOLOGIN
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
    INHERIT;
END
$review$;

GRANT CONNECT ON DATABASE investment_lab TO isl_legacy_history_reader;
GRANT USAGE ON SCHEMA investment_lab TO isl_legacy_history_reader;

-- The existing legacy table contains public market reference series only.
-- The connector selects a strict seven-column subset and an instrument
-- allowlist. PostgreSQL SELECT is table-scoped here because the existing
-- runtime ACL gate uses has_table_privilege(role, ..., 'SELECT').
GRANT SELECT ON TABLE investment_lab.price_observations
  TO isl_legacy_history_reader;

-- Deliberately no grants on holdings, private valuations, paper events,
-- journals, or ANY source/agent tables. No DML/DDL and no LOGIN.
DO $verify$
BEGIN
  IF (SELECT rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls
      FROM pg_roles WHERE rolname='isl_legacy_history_reader')
     OR NOT has_table_privilege(
       'isl_legacy_history_reader','investment_lab.price_observations','SELECT')
     OR has_table_privilege(
       'isl_legacy_history_reader','investment_lab.price_observations',
       'INSERT,UPDATE,DELETE,TRUNCATE')
     OR has_table_privilege(
       'isl_legacy_history_reader','investment_lab.holding_snapshots','SELECT')
     OR has_table_privilege(
       'isl_legacy_history_reader','investment_lab.valuations','SELECT')
     OR has_table_privilege(
       'isl_legacy_history_reader','investment_lab.paper_events','SELECT')
     OR has_table_privilege(
       'isl_legacy_history_reader','investment_lab.agent_cycles','INSERT')
     OR has_database_privilege(
       'isl_legacy_history_reader','investment_lab','CREATE')
     OR has_schema_privilege(
       'isl_legacy_history_reader','investment_lab','CREATE')
  THEN
    RAISE EXCEPTION 'Historical reader least-privilege policy failed';
  END IF;
END
$verify$;
