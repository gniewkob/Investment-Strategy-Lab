-- DISPOSABLE POSTGRESQL CI FIXTURE ONLY. DO NOT APPLY TO NEON OR PRODUCTION.
-- Exact existing reviewed v2 migration 007 from unmerged draft PR #1.
-- Used only in a synthetic local PostgreSQL service with fake roles and data.

-- Investment Strategy Lab v2, Sprint 1. Additive, no changes to legacy prices.
-- PIT/point-in-time consumers MUST use prices_asof(timestamp) instead of price_observations.
CREATE TABLE IF NOT EXISTS investment_lab.source_documents (
  document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_code text NOT NULL REFERENCES investment_lab.data_sources(source_code),
  canonical_url text NOT NULL CHECK (canonical_url ~ '^https://'),
  sha256_hex text NOT NULL CHECK (sha256_hex ~ '^[a-f0-9]{64}$'),
  published_at timestamptz NOT NULL,
  publication_precision text NOT NULL CHECK (publication_precision IN ('EXACT','DAY')),
  retrieved_at timestamptz NOT NULL DEFAULT now(),
  content_type text NOT NULL DEFAULT 'application/octet-stream',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata)='object'),
  UNIQUE (source_code, canonical_url, sha256_hex),
  CHECK (retrieved_at >= published_at)
);
CREATE INDEX IF NOT EXISTS source_documents_published_idx
  ON investment_lab.source_documents(source_code,published_at DESC);

CREATE TABLE IF NOT EXISTS investment_lab.price_observation_versions (
  version_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  instrument_code text NOT NULL REFERENCES investment_lab.instruments(instrument_code),
  source_code text NOT NULL REFERENCES investment_lab.data_sources(source_code),
  observed_for timestamptz NOT NULL,
  interval_code text NOT NULL CHECK (interval_code IN ('1d','1w','1mo','spot')),
  revision_no integer NOT NULL CHECK (revision_no>=1),
  document_id uuid NOT NULL REFERENCES investment_lab.source_documents(document_id),
  price_value numeric NOT NULL CHECK (price_value > 0),
  value_concept text NOT NULL CHECK (value_concept IN ('DAILY_SPOT','MONTHLY_AVERAGE','FX_REFERENCE','OTHER_REFERENCE')),
  -- available_at = moment it could legitimately be known by a model (not observed_for).
  -- For DAY-precision publication dates, use NEXT day's 00:00 UTC conservatively.
  available_at timestamptz NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  note text NOT NULL DEFAULT '',
  UNIQUE (instrument_code,source_code,observed_for,interval_code,revision_no),
  UNIQUE (instrument_code,source_code,observed_for,interval_code,document_id),
  CHECK (available_at >= observed_for),
  CHECK (recorded_at >= available_at)
);
CREATE INDEX IF NOT EXISTS price_versions_pit_idx
  ON investment_lab.price_observation_versions(instrument_code,source_code,observed_for,available_at DESC,revision_no DESC);

-- Public release and local receipt/ingestion gates reside in a SQL SECURITY INVOKER function.
-- A quote known publicly before an experiment but fetched later is not available
-- to the autonomous agent on that historical run date. Do not backfill "known" records retroactively.
-- All research reads MUST call prices_asof(cutoff). The function also enforces
-- conservative NEXT-DAY availability for documents with DAY-precision dates.
CREATE OR REPLACE FUNCTION investment_lab.prices_asof(cutoff timestamptz)
RETURNS TABLE(instrument_code text,source_code text,observed_for timestamptz,
              interval_code text,price_value numeric,value_concept text,
              revision_no integer,available_at timestamptz,document_id uuid)
LANGUAGE sql STABLE SECURITY INVOKER AS '
SELECT DISTINCT ON (v.instrument_code,v.source_code,v.observed_for,v.interval_code)
  v.instrument_code,v.source_code,v.observed_for,v.interval_code,v.price_value,
  v.value_concept,v.revision_no,
  GREATEST(v.available_at,CASE WHEN s.publication_precision=''DAY''
    THEN (((s.published_at AT TIME ZONE ''UTC'')::date+1)::timestamp AT TIME ZONE ''UTC'')
    ELSE s.published_at END, v.recorded_at, s.retrieved_at),
  v.document_id
FROM investment_lab.price_observation_versions v
JOIN investment_lab.source_documents s USING(document_id)
WHERE s.source_code = v.source_code
  AND GREATEST(v.available_at,CASE WHEN s.publication_precision=''DAY''
    THEN (((s.published_at AT TIME ZONE ''UTC'')::date+1)::timestamp AT TIME ZONE ''UTC'')
    ELSE s.published_at END, v.recorded_at, s.retrieved_at) <= cutoff
ORDER BY v.instrument_code,v.source_code,v.observed_for,v.interval_code,
         GREATEST(v.available_at,CASE WHEN s.publication_precision=''DAY''
    THEN (((s.published_at AT TIME ZONE ''UTC'')::date+1)::timestamp AT TIME ZONE ''UTC'')
    ELSE s.published_at END, v.recorded_at, s.retrieved_at) DESC, v.revision_no DESC
';

CREATE TABLE IF NOT EXISTS investment_lab.pipeline_runs (
  run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_key text NOT NULL UNIQUE CHECK (length(run_key) BETWEEN 8 AND 180),
  pipeline_name text NOT NULL,
  code_version text NOT NULL,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  status text NOT NULL DEFAULT 'STARTED' CHECK (status IN ('STARTED','SUCCEEDED','FAILED','SKIPPED')),
  input_fingerprint text CHECK (input_fingerprint IS NULL OR input_fingerprint ~ '^[a-f0-9]{64}$'),
  rows_received integer NOT NULL DEFAULT 0 CHECK(rows_received>=0),
  rows_inserted integer NOT NULL DEFAULT 0 CHECK(rows_inserted>=0),
  rows_revised integer NOT NULL DEFAULT 0 CHECK(rows_revised>=0),
  error_summary text,
  CHECK (finished_at IS NULL OR finished_at>=started_at),
  CHECK ((status='STARTED')=(finished_at IS NULL))
);
CREATE INDEX IF NOT EXISTS pipeline_runs_status_idx
 ON investment_lab.pipeline_runs(pipeline_name,started_at DESC);

CREATE TABLE IF NOT EXISTS investment_lab.pipeline_run_events (
  event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id uuid NOT NULL REFERENCES investment_lab.pipeline_runs(run_id),
  created_at timestamptz NOT NULL DEFAULT now(),
  severity text NOT NULL CHECK (severity IN ('INFO','WARNING','ERROR')),
  event_code text NOT NULL,
  details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK(jsonb_typeof(details)='object')
);
CREATE INDEX IF NOT EXISTS pipeline_run_events_idx
 ON investment_lab.pipeline_run_events(run_id,created_at);
