-- Working Engine v0.3 as-of independently READ-ONLY verification.
-- Recomputes SQL-input evidence; never inserts, updates or deletes rows.
WITH
clock AS (
  SELECT CASE
    WHEN now() >= ((date_trunc('day',now() AT TIME ZONE 'UTC') + interval '19 hours') AT TIME ZONE 'UTC')
      THEN (date_trunc('day',now() AT TIME ZONE 'UTC') + interval '19 hours') AT TIME ZONE 'UTC'
    ELSE (date_trunc('day',now() AT TIME ZONE 'UTC') - interval '5 hours') AT TIME ZONE 'UTC'
  END AS cutoff
),
models AS (
  SELECT m.model_code,v.version_no,v.rules
  FROM investment_lab.models AS m
  JOIN LATERAL (
    SELECT version_no,rules
    FROM investment_lab.model_versions AS v
    WHERE v.model_code=m.model_code
    ORDER BY version_no DESC LIMIT 1
  ) AS v ON TRUE
  WHERE m.model_code IN ('M1_GLOBAL_EQ','M2_DIVERSIFIED','M3_TACTICAL')
    AND m.simulation_only=true AND m.base_currency='PLN'
),
eligible AS (
  SELECT p.instrument_code,p.source_code,p.observed_for,p.ingested_at,
         p.interval_code,p.return_basis,p.close_price,i.quote_currency,p.source_url
  FROM investment_lab.price_observations AS p
  JOIN investment_lab.instruments AS i USING (instrument_code)
  CROSS JOIN clock
  WHERE p.ingested_at<=clock.cutoff AND p.observed_for<=clock.cutoff
),
latest AS (
  SELECT DISTINCT ON (instrument_code)
      instrument_code,source_code,observed_for,ingested_at,interval_code,
      return_basis,close_price,quote_currency,source_url
  FROM eligible
  ORDER BY instrument_code,observed_for DESC,ingested_at DESC,source_code
),
prices_summary AS (SELECT count(*) AS eligible_rows FROM eligible),
all_eligible_digest AS (
  -- Every as-of input observation, not just each instrument's latest price.
  -- Deterministic ordering avoids nondeterminism across query plans.
  -- A historical non-latest price mutation MUST invalidate same-cutoff replay.
  SELECT encode(sha256(convert_to(coalesce(jsonb_agg(
     jsonb_build_array(instrument_code,source_code,observed_for,ingested_at,
                       interval_code,return_basis,close_price,quote_currency,source_url)
     ORDER BY instrument_code,source_code,observed_for,ingested_at,
              interval_code,return_basis,close_price,source_url
  ),'[]'::jsonb)::text,'UTF8')),'hex') AS all_rows_sha256
  FROM eligible
),
source_manifest AS (
  SELECT coalesce(jsonb_agg(jsonb_build_object(
    'instrument_code',instrument_code,'source_code',source_code,
    'observed_for',observed_for,'ingested_at',ingested_at,
    'interval_code',interval_code,'return_basis',return_basis,
    'quote_currency',quote_currency,'close_price',close_price,
    'source_url',source_url
  ) ORDER BY instrument_code),'[]'::jsonb) AS rows
  FROM latest
),
required(model_code,instrument_code) AS (
  VALUES
  ('M1_GLOBAL_EQ','GLOBAL_EQUITY_TR_PLN'),
  ('M2_DIVERSIFIED','GLOBAL_EQUITY_TR_PLN'),
  ('M2_DIVERSIFIED','PL_BONDS_TR_PLN'),
  ('M2_DIVERSIFIED','GOLD_TR_PLN'),
  ('M3_TACTICAL','GLOBAL_EQUITY_TR_PLN'),
  ('M3_TACTICAL','PL_BONDS_TR_PLN'),
  ('M3_TACTICAL','GOLD_TR_PLN')
),
missing AS (
  SELECT m.model_code,
   coalesce(jsonb_agg(r.instrument_code ORDER BY r.instrument_code) FILTER (
      WHERE l.instrument_code IS NULL OR l.return_basis <> 'TOTAL_RETURN'
       OR l.quote_currency <> 'PLN' OR l.interval_code <> '1mo'
   ),'[]'::jsonb) AS missing_series
  FROM models AS m
  JOIN required AS r USING (model_code)
  LEFT JOIN latest AS l USING (instrument_code)
  GROUP BY m.model_code
),
nbp_catalog(instrument_code,source_code,return_basis) AS (
 VALUES ('USDPLN_NBP','nbp_rates','FX_RATE'),
        ('EURPLN_NBP','nbp_rates','FX_RATE'),
        ('GOLD_NBP_PLN_G','nbp_gold','PRICE_ONLY')
),
nbp_ranked AS (
 SELECT e.*,
        row_number() OVER (PARTITION BY e.instrument_code
                           ORDER BY e.observed_for DESC,e.ingested_at DESC,
                                    e.source_code) AS n
 FROM eligible e JOIN nbp_catalog n
   ON n.instrument_code=e.instrument_code
  AND n.source_code=e.source_code AND n.return_basis=e.return_basis
 WHERE e.interval_code='1d' AND e.quote_currency='PLN' AND e.close_price>0
   AND e.source_url LIKE 'https://api.nbp.pl/api/%'
),
nbp_stats AS (
 SELECT c.instrument_code,c.source_code,c.return_basis,
        count(r.n) AS observations,
        max(r.observed_for) FILTER (WHERE r.n=1) AS last_observed,
        max(r.ingested_at) FILTER (WHERE r.n=1) AS last_ingested,
        max(r.close_price) FILTER (WHERE r.n=1) AS latest_value,
        max(r.close_price) FILTER (WHERE r.n=6) AS five_ago,
        max(r.close_price) FILTER (WHERE r.n=21) AS twenty_ago,
        min(r.close_price) AS window_min,
        max(r.close_price) AS window_max,
        encode(sha256(convert_to(coalesce(jsonb_agg(
          jsonb_build_array(r.observed_for,r.ingested_at,r.close_price,r.source_url)
          ORDER BY r.observed_for,r.ingested_at,r.source_url
        ) FILTER (WHERE r.n IS NOT NULL),'[]'::jsonb)::text,'UTF8')),'hex')
          AS window_sha256
 FROM nbp_catalog c LEFT JOIN nbp_ranked r
    ON r.instrument_code=c.instrument_code AND r.n<=21
 GROUP BY c.instrument_code,c.source_code,c.return_basis
),
nbp_scored AS (
 SELECT s.*,
   CASE WHEN s.last_observed IS NULL THEN 'SOURCE_MISSING_AT_CUTOFF'
        WHEN (clock.cutoff::date-s.last_observed::date)>7
          THEN 'SOURCE_STALE_AT_CUTOFF'
        WHEN s.observations<21 THEN 'REFERENCE_WINDOW_SHORT_AT_CUTOFF'
        ELSE 'SOURCE_RECENT_AT_CUTOFF' END AS reference_status
 FROM nbp_stats s CROSS JOIN clock
),
nbp_context AS (
 SELECT coalesce(jsonb_agg(jsonb_build_object(
   'instrument_code',s.instrument_code,'source_code',s.source_code,
   'return_basis',s.return_basis,'currency','PLN',
   'observations_in_window',s.observations,'last_observed',s.last_observed,
   'last_ingested',s.last_ingested,'latest_value',s.latest_value,
   'change_five_observations_pct',CASE WHEN s.observations>=6
        THEN round(100*(s.latest_value/s.five_ago-1),4) ELSE NULL END,
   'change_twenty_observations_pct',CASE WHEN s.observations>=21
        THEN round(100*(s.latest_value/s.twenty_ago-1),4) ELSE NULL END,
   'range_twenty_observations_pct',CASE WHEN s.observations>=21
        THEN round(100*(s.window_max/s.window_min-1),4) ELSE NULL END,
   'window_sha256',s.window_sha256,'status_at_cutoff',s.reference_status,
   'interpretation','DESCRIPTIVE_REFERENCE_ONLY_NOT_TOTAL_RETURN')
   ORDER BY s.instrument_code),'[]'::jsonb) AS reference_rows,
   CASE WHEN bool_and(s.reference_status='SOURCE_RECENT_AT_CUTOFF')
         THEN 'REFERENCE_RECENT_AT_CUTOFF'
         ELSE 'REFERENCE_INCOMPLETE_AT_CUTOFF' END AS reference_status
 FROM nbp_scored s
),
paper_ledger_rows AS (
 SELECT m.model_code,
   coalesce(jsonb_agg(jsonb_build_array(
     e.event_id,e.event_time,e.recorded_at,e.event_kind,e.gross_amount,e.fee_amount
     ) ORDER BY e.event_time,e.recorded_at,e.event_id)
     FILTER (WHERE e.event_id IS NOT NULL),'[]'::jsonb) AS events
 FROM models m CROSS JOIN clock
 LEFT JOIN investment_lab.paper_events e ON e.model_code=m.model_code
   AND e.event_time<=clock.cutoff AND e.recorded_at<=clock.cutoff
 GROUP BY m.model_code
),
paper_ledger AS (
 SELECT model_code,events,
  encode(sha256(convert_to(events::text,'UTF8')),'hex') AS ledger_sha256
 FROM paper_ledger_rows
),
paper AS (
  SELECT m.model_code,
   coalesce(sum(e.gross_amount) FILTER (
     WHERE e.event_kind='VIRTUAL_CONTRIBUTION'),0) AS contributions_pln,
   coalesce(sum(e.fee_amount),0) AS booked_fees,
   count(e.event_id) FILTER (
     WHERE e.event_kind IN ('PAPER_BUY','PAPER_SELL')) AS prior_fills
  FROM models m
  CROSS JOIN clock
  LEFT JOIN investment_lab.paper_events e ON e.model_code=m.model_code
    AND e.event_time<=clock.cutoff AND e.recorded_at<=clock.cutoff
  GROUP BY m.model_code
),
prepared AS (
  SELECT m.model_code,m.version_no,m.rules,clock.cutoff,
   md5('isl-engine-v03-run|'||m.model_code||'|'||clock.cutoff::text)::uuid AS run_id,
   md5('isl-engine-v03-signal|'||m.model_code||'|'||clock.cutoff::text)::uuid AS signal_id,
   missing.missing_series,paper.contributions_pln,paper.booked_fees,paper.prior_fills,
   prices_summary.eligible_rows,source_manifest.rows AS sources,
   all_eligible_digest.all_rows_sha256 AS source_digest,
   nbp_context.reference_rows AS reference_context,
   nbp_context.reference_status AS reference_status_at_cutoff,
   paper_ledger.events AS paper_ledger,
   paper_ledger.ledger_sha256 AS paper_ledger_sha256,
   jsonb_build_object(
      'engine_version','v03','model_code',m.model_code,'model_version',m.version_no,
      'cutoff_utc',clock.cutoff,'model_rules',m.rules,
      'eligible_market_rows',prices_summary.eligible_rows,
      'all_eligible_market_rows_sha256',all_eligible_digest.all_rows_sha256,
      'latest_market_references',source_manifest.rows,
      'nbp_reference_context',nbp_context.reference_rows,
      'nbp_reference_status_at_cutoff',nbp_context.reference_status,
      'paper_event_ledger',paper_ledger.events,
      'paper_event_ledger_sha256',paper_ledger.ledger_sha256,
      'missing_total_return_series',missing.missing_series,
      'virtual_contributions_pln',paper.contributions_pln,
      'booked_fees_pln',paper.booked_fees,'historical_paper_fills',paper.prior_fills
   ) AS evidence
  FROM models m
  JOIN missing USING(model_code)
  JOIN paper USING(model_code)
  CROSS JOIN clock CROSS JOIN prices_summary CROSS JOIN source_manifest
  CROSS JOIN all_eligible_digest CROSS JOIN nbp_context
  JOIN paper_ledger ON paper_ledger.model_code=m.model_code
),
sealed AS (
 SELECT p.*,encode(sha256(convert_to(p.evidence::text,'UTF8')),'hex') AS input_hash,
        CASE WHEN p.missing_series='[]'::jsonb
              THEN 'RESEARCH_ONLY' ELSE 'INSUFFICIENT_DATA' END AS verdict
 FROM prepared p
),
recorded AS (
 SELECT p.*,
        r.status AS stored_status,
        r.run_id AS stored_run_id,
        r.reproducibility_hash AS stored_input_hash,
        r.metrics AS stored_metrics,
        r.assumptions->>'engine' AS stored_engine
 FROM sealed p
 LEFT JOIN investment_lab.research_runs r ON r.run_id=p.run_id
),
cross_checks AS (
 SELECT p.*,
        s.signal_rows,s.signal_match,s.signal_engine_matches,
        a.audit_rows,a.audit_match,a.audit_paper_only_matches,
        f.paper_fills
 FROM recorded p
 LEFT JOIN LATERAL (
   SELECT count(*) AS signal_rows,
          bool_and(e.components->>'input_sha256'=p.input_hash
                   AND e.components->>'paper_event_ledger_sha256'=p.paper_ledger_sha256
                   AND e.verdict=p.verdict) AS signal_match,
          bool_and(e.components->>'engine'='working-engine-v03') AS signal_engine_matches
   FROM investment_lab.signal_events e
   WHERE e.components->>'run_id'=p.run_id::text
 ) s ON TRUE
 LEFT JOIN LATERAL (
   SELECT count(*) AS audit_rows,
          bool_and(a.metadata->>'input_sha256'=p.input_hash
                   AND a.metadata->>'paper_event_ledger_sha256'=p.paper_ledger_sha256
                   AND a.metadata->>'signal_verdict'=p.verdict) AS audit_match,
          bool_and(a.metadata->>'research_paper_only'='true'
                   AND a.metadata->>'financial_operations'='0') AS audit_paper_only_matches
   FROM investment_lab.audit_events a
   WHERE a.record_id=p.run_id::text
 ) a ON TRUE
 CROSS JOIN LATERAL (
    SELECT count(*) AS paper_fills
    FROM investment_lab.paper_events
    WHERE event_kind IN ('PAPER_BUY','PAPER_SELL')
 ) f
)
SELECT model_code,cutoff,run_id,
       CASE WHEN stored_run_id IS NULL THEN 'CYCLE_MISSING'
            WHEN stored_input_hash IS DISTINCT FROM input_hash
              OR stored_metrics->>'all_eligible_market_rows_sha256'
                   IS DISTINCT FROM source_digest
              OR stored_metrics->>'paper_event_ledger_sha256'
                   IS DISTINCT FROM paper_ledger_sha256
              OR stored_metrics->'nbp_reference_context'
                   IS DISTINCT FROM reference_context
              OR stored_metrics->'paper_event_ledger'
                   IS DISTINCT FROM paper_ledger
              OR stored_metrics->>'nbp_reference_status_at_cutoff'
                   IS DISTINCT FROM reference_status_at_cutoff
                 THEN 'SOURCE_OR_LEDGER_INPUT_CHANGED'
            WHEN stored_status<>'COMPLETED'
              OR stored_engine<>'working-engine-v03'
              OR signal_rows<>1 OR audit_rows<>1
              OR signal_match IS NOT TRUE OR audit_match IS NOT TRUE
              OR signal_engine_matches IS NOT TRUE
              OR audit_paper_only_matches IS NOT TRUE
              OR stored_metrics->>'real_financial_operations'<>'0'
              OR stored_metrics->>'new_paper_events'<>'0'
                 THEN 'CYCLE_INVALID'
            ELSE 'ENGINE_OK' END AS engine_status,
       verdict AS evaluated_verdict,reference_status_at_cutoff,
       eligible_rows,source_digest AS recomputed_market_sha256,
       paper_ledger_sha256 AS recomputed_paper_ledger_sha256,
       stored_input_hash,input_hash AS recomputed_input_sha256,
       signal_rows,audit_rows,paper_fills,
       0 AS paper_events_created,0 AS financial_operations
FROM cross_checks
ORDER BY model_code;
