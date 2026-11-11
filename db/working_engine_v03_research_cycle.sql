-- Working Engine v0.3: complete market-input fingerprint, append-only research.
-- Separate v0.2 key namespace preserves existing v0.1 cycles and the currently
-- pinned live scheduler. No paper or real trade execution.
-- Research-only execution on the private lab branch (main) or a test clone.
-- No production environment exists. Disposable tests must run only locally.
-- No brokerage integration, no virtual fills, no cash contributions, no trades.
-- Serialize all evidence timestamps in UTC to make hashes independent of
-- the PostgreSQL session TimeZone (legacy UTC JSON representation retained).
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
     jsonb_build_array(instrument_code,source_code,(replace((observed_for AT TIME ZONE 'UTC')::text,' ','T') || '+00:00'),(replace((ingested_at AT TIME ZONE 'UTC')::text,' ','T') || '+00:00'),
                       interval_code,return_basis,close_price,quote_currency,source_url)
     ORDER BY instrument_code,source_code,observed_for,ingested_at,
              interval_code,return_basis,close_price,source_url
  ),'[]'::jsonb)::text,'UTF8')),'hex') AS all_rows_sha256
  FROM eligible
),
source_manifest AS (
  SELECT coalesce(jsonb_agg(jsonb_build_object(
    'instrument_code',instrument_code,'source_code',source_code,
    'observed_for',(replace((observed_for AT TIME ZONE 'UTC')::text,' ','T') || '+00:00'),'ingested_at',(replace((ingested_at AT TIME ZONE 'UTC')::text,' ','T') || '+00:00'),
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
          jsonb_build_array((replace((r.observed_for AT TIME ZONE 'UTC')::text,' ','T') || '+00:00'),(replace((r.ingested_at AT TIME ZONE 'UTC')::text,' ','T') || '+00:00'),r.close_price,r.source_url)
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
        WHEN ((clock.cutoff AT TIME ZONE 'UTC')::date-(s.last_observed AT TIME ZONE 'UTC')::date)>7
          THEN 'SOURCE_STALE_AT_CUTOFF'
        WHEN s.observations<21 THEN 'REFERENCE_WINDOW_SHORT_AT_CUTOFF'
        ELSE 'SOURCE_RECENT_AT_CUTOFF' END AS reference_status
 FROM nbp_stats s CROSS JOIN clock
),
nbp_context AS (
 SELECT coalesce(jsonb_agg(jsonb_build_object(
   'instrument_code',s.instrument_code,'source_code',s.source_code,
   'return_basis',s.return_basis,'currency','PLN',
   'observations_in_window',s.observations,'last_observed',(replace((s.last_observed AT TIME ZONE 'UTC')::text,' ','T') || '+00:00'),
   'last_ingested',(replace((s.last_ingested AT TIME ZONE 'UTC')::text,' ','T') || '+00:00'),'latest_value',s.latest_value,
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
     e.event_id,(replace((e.event_time AT TIME ZONE 'UTC')::text,' ','T') || '+00:00'),(replace((e.recorded_at AT TIME ZONE 'UTC')::text,' ','T') || '+00:00'),e.event_kind,e.gross_amount,e.fee_amount
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
   md5('isl-engine-v03-run|'||m.model_code||'|'||((clock.cutoff AT TIME ZONE 'UTC')::text || '+00'))::uuid AS run_id,
   md5('isl-engine-v03-signal|'||m.model_code||'|'||((clock.cutoff AT TIME ZONE 'UTC')::text || '+00'))::uuid AS signal_id,
   missing.missing_series,paper.contributions_pln,paper.booked_fees,paper.prior_fills,
   prices_summary.eligible_rows,source_manifest.rows AS sources,
   all_eligible_digest.all_rows_sha256 AS source_digest,
   nbp_context.reference_rows AS reference_context,
   nbp_context.reference_status AS reference_status_at_cutoff,
   paper_ledger.events AS paper_ledger,
   paper_ledger.ledger_sha256 AS paper_ledger_sha256,
   jsonb_build_object(
      'engine_version','v03','model_code',m.model_code,'model_version',m.version_no,
      'cutoff_utc',(replace((clock.cutoff AT TIME ZONE 'UTC')::text,' ','T') || '+00:00'),'model_rules',m.rules,
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
preexisting AS (
 SELECT x.run_id,x.reproducibility_hash
 FROM investment_lab.research_runs x
 WHERE x.run_id IN (SELECT run_id FROM sealed)
),
inserted_runs AS (
 INSERT INTO investment_lab.research_runs
 (run_id,model_code,version_no,evaluated_at,input_cutoff,status,
  data_sources,assumptions,metrics,findings,reproducibility_hash)
 SELECT p.run_id,p.model_code,p.version_no,now(),p.cutoff,'COMPLETED',
        p.sources,
        jsonb_build_object('engine','working-engine-v03','paper_only',true,
          'no_execution_api',true,'model_rules',p.rules,
          'source_availability','ingested_at_and_observed_for_not_after_cutoff',
          'no_historical_vintage_certification',true),
        jsonb_build_object('verdict',p.verdict,
          'missing_series',p.missing_series,
          'eligible_market_rows',p.eligible_rows,
          'all_eligible_market_rows_sha256',p.source_digest,
          'nbp_reference_context',p.reference_context,
          'nbp_reference_status_at_cutoff',p.reference_status_at_cutoff,
          'paper_event_ledger',p.paper_ledger,
          'paper_event_ledger_sha256',p.paper_ledger_sha256,
          'virtual_contributions_pln',p.contributions_pln,
          'booked_fees_pln',p.booked_fees,'prior_paper_fills',p.prior_fills,
          'cash_pln_if_no_fills',CASE WHEN p.prior_fills=0
                   THEN p.contributions_pln-p.booked_fees ELSE NULL END,
          'new_paper_events',0,'real_financial_operations',0),
        'Research cycle executed on live-source Neon snapshot; '
           ||CASE WHEN p.missing_series='[]'::jsonb
                   THEN 'research-only candidate, no fill execution'
                   ELSE 'required verified PLN total-return series missing; HOLD_CASH' END,
        p.input_hash
 FROM sealed p
 WHERE NOT EXISTS (SELECT 1 FROM preexisting e
                   WHERE e.run_id=p.run_id AND e.reproducibility_hash<>p.input_hash)
 ON CONFLICT (run_id) DO NOTHING
 RETURNING run_id,model_code
),
inserted_signals AS (
 INSERT INTO investment_lab.signal_events
 (signal_id,model_code,version_no,generated_at,data_cutoff,verdict,
  evidence_score,components,explanation,invalidation_condition,source_summary)
 SELECT p.signal_id,p.model_code,p.version_no,now(),p.cutoff,p.verdict,
        NULL,
        jsonb_build_object('engine','working-engine-v03',
          'run_id',p.run_id::text,'input_sha256',p.input_hash,
          'missing_series',p.missing_series,'new_paper_events',0,
          'nbp_reference_status_at_cutoff',p.reference_status_at_cutoff,
          'paper_event_ledger_sha256',p.paper_ledger_sha256),
        CASE WHEN p.verdict='INSUFFICIENT_DATA'
            THEN 'HOLD_CASH: verified PLN total-return series unavailable'
            ELSE 'RESEARCH_ONLY: no historical fill/fee validation; no execution' END,
        'Re-evaluate on new source evidence; never infer a fill from an index.',
        'Read-only Neon market snapshot, limited by observed_for and ingested_at'
 FROM sealed p JOIN inserted_runs r USING(run_id)
 ON CONFLICT (signal_id) DO NOTHING
 RETURNING signal_id,model_code
),
inserted_audit AS (
 INSERT INTO investment_lab.audit_events
 (kind,record_id,message,metadata)
 SELECT 'VALIDATION',p.run_id::text,
        'Working Engine v0.3 completed research cycle without financial execution',
        jsonb_build_object('model_code',p.model_code,
           'input_sha256',p.input_hash,'cutoff',(replace((p.cutoff AT TIME ZONE 'UTC')::text,' ','T') || '+00:00'),
           'signal_verdict',p.verdict,'new_paper_events',0,
           'nbp_reference_status_at_cutoff',p.reference_status_at_cutoff,
           'paper_event_ledger_sha256',p.paper_ledger_sha256,
           'research_paper_only',true,'financial_operations',0)
 FROM sealed p JOIN inserted_runs r USING(run_id)
 RETURNING audit_id,record_id
)
SELECT p.model_code,p.version_no,p.cutoff,p.run_id,p.input_hash,
       p.verdict,p.missing_series,p.eligible_rows,p.contributions_pln,
       p.booked_fees,p.prior_fills,
       CASE WHEN e.run_id IS NOT NULL AND e.reproducibility_hash<>p.input_hash
            THEN 'REPLAY_INPUT_COLLISION'
            WHEN r.run_id IS NOT NULL THEN 'NEW_RESEARCH_RUN'
            ELSE 'IDEMPOTENT_REPLAY' END AS persistence_state,
       (SELECT count(*) FROM inserted_runs) AS research_runs_added,
       (SELECT count(*) FROM inserted_signals) AS signals_added,
       (SELECT count(*) FROM inserted_audit) AS audit_rows_added,
       0 AS paper_events_created,0 AS financial_operations,
       p.source_digest AS all_eligible_market_rows_sha256,
       p.reference_status_at_cutoff AS nbp_reference_status_at_cutoff,
       p.paper_ledger_sha256 AS paper_event_ledger_sha256
FROM sealed p
LEFT JOIN preexisting e USING(run_id)
LEFT JOIN inserted_runs r USING(run_id)
ORDER BY p.model_code;
