-- Investment Strategy Lab P0 — EIA first current-vintage snapshot
-- STAGING READ-ONLY DATA PREFLIGHT. No DDL/DML, no role grant, no writes.
--
-- This SQL verifies LOCAL Neon state only. It cannot inspect live EIA HTTPS,
-- original HTML evidence, protected GitHub environment secrets, branch ID
-- identity, or a human approval. It MUST NOT return an import GO decision.
-- Run ONLY against confirmed isolated Neon STAGING:
-- project red-lake-53043722 / branch br-wandering-union-ba6ogf6l
-- database investment_lab. Never run this as evidence of production readiness.
--
-- The 660-row checksum is the independently verified original legacy slice.
-- It is NOT the SHA-256 of EIA HTML or of any PIT source document.
WITH
source_catalog AS (
  SELECT COUNT(*) AS n
  FROM investment_lab.data_sources
  WHERE source_code IN ('eia_wti_daily','eia_brent_daily','eia_henryhub_daily')
),
instrument_catalog AS (
  SELECT COUNT(*) AS n
  FROM investment_lab.instruments
  WHERE instrument_code IN
    ('WTI_EIA_USD_BBL','BRENT_EIA_USD_BBL','HENRY_HUB_USD_MMBTU')
),
staging_marker AS (
  SELECT
    (SELECT COUNT(*) FROM investment_lab.agent_cycles
       WHERE run_key = 'staging-security-canary-2026-10-18') AS cycles,
    (SELECT COUNT(*) FROM investment_lab.agent_paper_decisions
       WHERE run_key = 'staging-security-canary-2026-10-18'
         AND decision_type='HOLD_CASH') AS paper_decisions
),
wti_counts AS (
  SELECT COUNT(*) AS n,
    COUNT(DISTINCT (observed_for AT TIME ZONE 'UTC')::date) AS unique_days,
    MIN((observed_for AT TIME ZONE 'UTC')::date) AS first_day,
    MAX((observed_for AT TIME ZONE 'UTC')::date) AS last_day,
    COUNT(*) FILTER (WHERE (observed_for AT TIME ZONE 'UTC')::date
      BETWEEN DATE '2026-08-26' AND DATE '2026-10-14') AS backfilled_35
  FROM investment_lab.price_observations
  WHERE instrument_code='WTI_EIA_USD_BBL'
),
legacy_660 AS (
  SELECT ENCODE(SHA256(CONVERT_TO(
    STRING_AGG(
      ((observed_for AT TIME ZONE 'UTC')::date)::text
        || ',' || close_price::text,
      E'\n' ORDER BY observed_for
    ), 'UTF8')), 'hex') AS frozen_original_660_sha256
  FROM investment_lab.price_observations
  WHERE instrument_code='WTI_EIA_USD_BBL'
    AND (observed_for AT TIME ZONE 'UTC')::date <= DATE '2026-08-25'
),
brent_counts AS (
  SELECT COUNT(*) AS n FROM investment_lab.price_observations
  WHERE instrument_code='BRENT_EIA_USD_BBL'
),
documents AS (
  SELECT
    COUNT(*) AS total_docs,
    COUNT(*) FILTER (WHERE source_code IN
      ('eia_wti_daily','eia_brent_daily','eia_henryhub_daily')) AS actual_eia_docs,
    COUNT(*) FILTER (WHERE source_code='nbp_gold') AS nbp_gold_docs
  FROM investment_lab.source_documents
),
versions AS (
  SELECT
    COUNT(*) AS total_versions,
    COUNT(*) FILTER (WHERE source_code IN
      ('eia_wti_daily','eia_brent_daily','eia_henryhub_daily')) AS eia_versions
  FROM investment_lab.price_observation_versions
),
writer_role AS (
  SELECT COUNT(*) AS present FROM pg_roles
  WHERE rolname='isl_eia_pit_staging_writer'
),
baseline AS (
  SELECT
    current_database() AS database_name,
    (SELECT n FROM source_catalog) AS source_catalog_n,
    (SELECT n FROM instrument_catalog) AS instrument_catalog_n,
    (SELECT cycles FROM staging_marker) AS staging_marker_cycles,
    (SELECT paper_decisions FROM staging_marker) AS staging_marker_decisions,
    (SELECT n FROM wti_counts) AS wti_rows,
    (SELECT unique_days FROM wti_counts) AS wti_unique_days,
    (SELECT first_day FROM wti_counts) AS first_wti,
    (SELECT last_day FROM wti_counts) AS last_wti,
    (SELECT backfilled_35 FROM wti_counts) AS wti_backfilled,
    (SELECT frozen_original_660_sha256 FROM legacy_660) AS frozen_sha,
    (SELECT n FROM brent_counts) AS brent_rows,
    (SELECT total_docs FROM documents) AS source_docs_total,
    (SELECT actual_eia_docs FROM documents) AS eia_docs_total,
    (SELECT nbp_gold_docs FROM documents) AS nbp_gold_docs,
    (SELECT total_versions FROM versions) AS pit_versions_total,
    (SELECT eia_versions FROM versions) AS eia_versions_total,
    (SELECT present FROM writer_role) AS eia_writer_roles
)
SELECT
  'EIA_FIRST_SNAPSHOT_STAGING_PREFLIGHT_V1' AS receipt_type,
  CASE
    WHEN database_name='investment_lab'
     AND source_catalog_n=3 AND instrument_catalog_n=3
     AND staging_marker_cycles=1 AND staging_marker_decisions=3
     AND wti_rows=695 AND wti_unique_days=695
     AND first_wti=DATE '2024-01-02'
     AND last_wti=DATE '2026-10-14'
     AND wti_backfilled=35
     AND frozen_sha=
       '2014f2ca99491cae91eafe3807d87300305ff201f82e24793aec21b2839862f8'
     AND brent_rows=706
    THEN 'REFERENCE_DATA_PREFLIGHT_PASS'
    ELSE 'REFERENCE_DATA_PREFLIGHT_FAIL'
  END AS local_reference_integrity,
  'NO_GO_PENDING_LIVE_SOURCE_AND_EXPLICIT_WRITER_APPROVAL' AS ingest_decision,
  database_name,source_catalog_n,instrument_catalog_n,
  staging_marker_cycles,staging_marker_decisions,
  wti_rows,wti_unique_days,first_wti,last_wti,wti_backfilled,
  frozen_sha AS immutable_original_660_sha256,brent_rows,
  source_docs_total,eia_docs_total,nbp_gold_docs,pit_versions_total,
  eia_versions_total,eia_writer_roles,
  FALSE AS latest_eia_html_provenance_verified_by_this_sql,
  FALSE AS github_workflow_manual_receipts_verified_by_this_sql,
  FALSE AS independent_historical_publication_vintages_verified,
  0 AS database_writes
FROM baseline;
