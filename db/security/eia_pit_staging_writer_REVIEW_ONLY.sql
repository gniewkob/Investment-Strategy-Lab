-- REVIEW ONLY: PostgreSQL role proposal for isolated Investment Strategy Lab STAGING.
-- NEVER auto-run on Neon, NEVER apply on production. NOLOGIN and no password.
-- Approval, platform audit, branch identity validation and final credential
-- provisioning are separate gates. CI only executes this on a disposable DB.
-- The staging canary is deliberately checked before role/GRANT DDL.

BEGIN;
DO $gate$
BEGIN
  IF current_database() <> 'investment_lab'
     OR (SELECT COUNT(*) FROM investment_lab.agent_cycles
         WHERE run_key='staging-security-canary-2026-10-18') <> 1
     OR (SELECT COUNT(*) FROM investment_lab.agent_paper_decisions
         WHERE run_key='staging-security-canary-2026-10-18'
           AND decision_type='HOLD_CASH') <> 3
  THEN
    RAISE EXCEPTION 'EIA_WRITER_REQUIRES_VERIFIED_STAGING_BRANCH_CANARY';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles
             WHERE rolname='isl_eia_pit_staging_writer') THEN
    RAISE EXCEPTION 'EIA_WRITER_ALREADY_EXISTS; AUDIT_MANUALLY';
  END IF;
  CREATE ROLE isl_eia_pit_staging_writer NOLOGIN
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
    NOBYPASSRLS INHERIT;
END
$gate$;

GRANT CONNECT ON DATABASE investment_lab TO isl_eia_pit_staging_writer;
GRANT USAGE ON SCHEMA investment_lab TO isl_eia_pit_staging_writer;
GRANT SELECT ON investment_lab.data_sources,
                investment_lab.instruments
  TO isl_eia_pit_staging_writer;
GRANT SELECT, INSERT ON investment_lab.source_documents,
                        investment_lab.price_observation_versions
  TO isl_eia_pit_staging_writer;

-- No DELETE, UPDATE, TRUNCATE, CREATE or ACL on legacy price table.
-- No portfolio/account, journal, broker, pipeline, or runtime permissions.
DO $verify$
DECLARE
  r record;
BEGIN
  SELECT * INTO r FROM pg_roles WHERE rolname='isl_eia_pit_staging_writer';
  IF r.rolname IS NULL OR r.rolcanlogin OR r.rolsuper
     OR r.rolcreatedb OR r.rolcreaterole OR r.rolbypassrls
     OR pg_has_role('isl_eia_pit_staging_writer','neon_superuser','MEMBER')
     OR has_database_privilege('isl_eia_pit_staging_writer','investment_lab','CREATE')
     OR has_schema_privilege('isl_eia_pit_staging_writer','investment_lab','CREATE')
     OR NOT has_table_privilege('isl_eia_pit_staging_writer',
                               'investment_lab.source_documents','SELECT')
     OR NOT has_table_privilege('isl_eia_pit_staging_writer',
                               'investment_lab.source_documents','INSERT')
     OR NOT has_table_privilege('isl_eia_pit_staging_writer',
                               'investment_lab.price_observation_versions','SELECT')
     OR NOT has_table_privilege('isl_eia_pit_staging_writer',
                               'investment_lab.price_observation_versions','INSERT')
     OR has_table_privilege('isl_eia_pit_staging_writer',
                           'investment_lab.source_documents','UPDATE,DELETE,TRUNCATE')
     OR has_table_privilege('isl_eia_pit_staging_writer',
                           'investment_lab.price_observation_versions','UPDATE,DELETE,TRUNCATE')
     OR has_table_privilege('isl_eia_pit_staging_writer',
                           'investment_lab.price_observations','SELECT,INSERT')
     OR has_table_privilege('isl_eia_pit_staging_writer',
                           'investment_lab.holding_snapshots','SELECT')
     OR has_table_privilege('isl_eia_pit_staging_writer',
                           'investment_lab.valuations','SELECT')
     OR has_table_privilege('isl_eia_pit_staging_writer',
                           'investment_lab.paper_events','SELECT')
     OR has_table_privilege('isl_eia_pit_staging_writer',
                           'investment_lab.agent_cycles','INSERT')
  THEN
    RAISE EXCEPTION 'EIA_WRITER_LEAST_PRIVILEGE_CONTRACT_FAILED';
  END IF;
END
$verify$;
COMMIT;
