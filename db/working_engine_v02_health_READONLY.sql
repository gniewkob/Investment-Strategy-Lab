-- Working Engine v0.2 — read-only independently recomputed source digest.
-- The private live LAB's v0.1 scheduler remains pinned to the original code.
-- Does not alter state, price, signal, audit, or paper event tables.
WITH
clock AS (
  SELECT now() AS checked_at,
   CASE
    WHEN now() >= ((date_trunc('day',now() AT TIME ZONE 'UTC') + interval '19 hours') AT TIME ZONE 'UTC')
      THEN (date_trunc('day',now() AT TIME ZONE 'UTC') + interval '19 hours') AT TIME ZONE 'UTC'
    ELSE (date_trunc('day',now() AT TIME ZONE 'UTC') - interval '5 hours') AT TIME ZONE 'UTC'
   END AS expected_cutoff
),
eligible AS (
  SELECT p.instrument_code,p.source_code,p.observed_for,p.ingested_at,
         p.interval_code,p.return_basis,p.close_price,i.quote_currency
  FROM investment_lab.price_observations p
  JOIN investment_lab.instruments i USING (instrument_code)
  CROSS JOIN clock c
  WHERE p.observed_for<=c.expected_cutoff
    AND p.ingested_at<=c.expected_cutoff
),
market_digest AS (
  -- Must mirror working_engine_v02_research_cycle.sql EXACTLY.
  SELECT count(*) AS eligible_rows,
    encode(sha256(convert_to(coalesce(jsonb_agg(
      jsonb_build_array(instrument_code,source_code,observed_for,ingested_at,
                        interval_code,return_basis,close_price,quote_currency)
      ORDER BY instrument_code,source_code,observed_for,ingested_at,
               interval_code,return_basis,close_price
    ),'[]'::jsonb)::text,'UTF8')),'hex') AS all_rows_sha256
  FROM eligible
),
required(model_code) AS (
  VALUES ('M1_GLOBAL_EQ'),('M2_DIVERSIFIED'),('M3_TACTICAL')
),
source_dates AS (
 SELECT
   max(observed_for) FILTER (WHERE instrument_code='USDPLN_NBP') AS usdpln_observed,
   max(observed_for) FILTER (WHERE instrument_code='EURPLN_NBP') AS eurpln_observed,
   max(observed_for) FILTER (WHERE instrument_code='GOLD_NBP_PLN_G') AS gold_observed,
   max(ingested_at) AS last_ingested
 FROM investment_lab.price_observations
),
paper_counts AS (
 SELECT count(*) FILTER (WHERE event_kind='VIRTUAL_CONTRIBUTION') AS contributions,
        count(*) FILTER (WHERE event_kind IN ('PAPER_BUY','PAPER_SELL')) AS paper_fills
 FROM investment_lab.paper_events
)
SELECT m.model_code, c.checked_at,c.expected_cutoff,
       r.run_id AS research_run_id,
       r.input_cutoff AS recorded_cutoff,
       r.metrics->>'verdict' AS research_verdict,
       md.eligible_rows AS recomputed_eligible_rows,
       md.all_rows_sha256 AS recomputed_market_sha256,
       r.metrics->>'all_eligible_market_rows_sha256' AS recorded_market_sha256,
       coalesce(s.matching_signals,0) AS signal_rows,
       coalesce(a.matching_audits,0) AS audit_rows,
       CASE WHEN r.run_id IS NULL THEN 'CYCLE_MISSING'
            WHEN r.metrics->>'all_eligible_market_rows_sha256' IS NULL
              THEN 'CYCLE_INVALID'
            WHEN r.metrics->>'all_eligible_market_rows_sha256'
                 IS DISTINCT FROM md.all_rows_sha256
              THEN 'SOURCE_INPUT_CHANGED'
            WHEN coalesce((r.metrics->>'eligible_market_rows')::bigint,-1)
                 <> md.eligible_rows
              THEN 'SOURCE_INPUT_CHANGED'
            WHEN r.status <> 'COMPLETED'
              OR r.input_cutoff<>c.expected_cutoff
              OR r.reproducibility_hash IS NULL
              OR coalesce(s.matching_signals,0)<>1
              OR coalesce(a.matching_audits,0)<>1
              OR coalesce(s.signal_hash_matches,false) IS NOT TRUE
              OR coalesce(a.audit_hash_matches,false) IS NOT TRUE
              OR coalesce(s.signal_verdict_matches,false) IS NOT TRUE
              OR coalesce(a.audit_has_paper_only_flag,false) IS NOT TRUE
              OR coalesce(r.metrics->>'real_financial_operations','')<>'0'
              OR coalesce(r.metrics->>'new_paper_events','')<>'0'
                 THEN 'CYCLE_INVALID'
            ELSE 'ENGINE_OK' END AS engine_status,
       CASE WHEN sd.usdpln_observed IS NULL
              OR sd.eurpln_observed IS NULL
              OR sd.gold_observed IS NULL THEN 'SOURCE_MISSING'
            WHEN (c.checked_at::date - sd.usdpln_observed::date)>7
              OR (c.checked_at::date - sd.eurpln_observed::date)>7
              OR (c.checked_at::date - sd.gold_observed::date)>7 THEN 'SOURCE_STALE'
            ELSE 'SOURCE_RECENT' END AS market_reference_status,
       sd.usdpln_observed,sd.eurpln_observed,sd.gold_observed,sd.last_ingested,
       pc.contributions AS total_alternative_contribution_events,
       pc.paper_fills AS total_paper_fills
FROM required m CROSS JOIN clock c CROSS JOIN source_dates sd
     CROSS JOIN paper_counts pc CROSS JOIN market_digest md
LEFT JOIN LATERAL (
 SELECT r.* FROM investment_lab.research_runs r
 WHERE r.model_code=m.model_code AND r.input_cutoff=c.expected_cutoff
   AND r.assumptions->>'engine'='working-engine-v02'
 ORDER BY r.evaluated_at DESC,r.run_id DESC LIMIT 1
) r ON TRUE
LEFT JOIN LATERAL (
 SELECT count(*) AS matching_signals,
        bool_and(s.components->>'input_sha256'=r.reproducibility_hash) AS signal_hash_matches,
        bool_and(s.verdict=r.metrics->>'verdict') AS signal_verdict_matches
 FROM investment_lab.signal_events s
 WHERE s.components->>'run_id'=r.run_id::text
) s ON TRUE
LEFT JOIN LATERAL (
 SELECT count(*) AS matching_audits,
        bool_and(a.metadata->>'input_sha256'=r.reproducibility_hash) AS audit_hash_matches,
        bool_and(a.metadata->>'research_paper_only'='true') AS audit_has_paper_only_flag
 FROM investment_lab.audit_events a
 WHERE a.record_id=r.run_id::text
) a ON TRUE
ORDER BY m.model_code;
