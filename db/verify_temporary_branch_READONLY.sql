-- Read-only acceptance queries for Investment Strategy Lab v2 Sprint 1 temporary Neon branch.
SELECT (SELECT count(*) FROM information_schema.tables WHERE table_schema='investment_lab' AND table_type='BASE TABLE') AS base_tables,
       (SELECT count(*) FROM investment_lab.price_observations) AS legacy_price_rows,
       (SELECT count(*) FROM investment_lab.source_documents) AS source_doc_count,
       (SELECT count(*) FROM investment_lab.price_observation_versions) AS version_count,
       (SELECT count(*) FROM investment_lab.pipeline_runs) AS pipeline_runs;
-- Synthetic revision test rows exist ONLY on the temporary branch.
SELECT 'before first available' AS check_name,price_value,revision_no FROM investment_lab.prices_asof('2026-09-29T23:59:59Z')
UNION ALL SELECT 'after first available',price_value,revision_no FROM investment_lab.prices_asof('2026-09-30T00:00:00Z')
UNION ALL SELECT 'before revision available',price_value,revision_no FROM investment_lab.prices_asof('2026-10-02T23:59:59Z')
UNION ALL SELECT 'after revision available',price_value,revision_no FROM investment_lab.prices_asof('2026-10-03T00:00:00Z');
