-- Working Engine v0.1: one bounded, idempotent, append-only research cycle.
-- Run ONLY on an isolated Neon acceptance/staging branch, never on main.
-- No brokerage integration, no virtual fills, no cash contributions, no trades.
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
         p.interval_code,p.return_basis,p.close_price,i.quote_currency
  FROM investment_lab.price_observations AS p
  JOIN investment_lab.instruments AS i USING (instrument_code)
  CROSS JOIN clock
  WHERE p.ingested_at<=clock.cutoff AND p.observed_for<=clock.cutoff
),
latest AS (
  SELECT DISTINCT ON (instrument_code)
      instrument_code,source_code,observed_for,ingested_at,interval_code,
      return_basis,close_price,quote_currency
  FROM eligible
  ORDER BY instrument_code,observed_for DESC,ingested_at DESC,source_code
),
prices_summary AS (SELECT count(*) AS eligible_rows FROM eligible),
source_manifest AS (
  SELECT coalesce(jsonb_agg(jsonb_build_object(
    'instrument_code',instrument_code,'source_code',source_code,
    'observed_for',observed_for,'ingested_at',ingested_at,
    'interval_code',interval_code,'return_basis',return_basis,
    'quote_currency',quote_currency,'close_price',close_price
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
   md5('isl-engine-v01-run|'||m.model_code||'|'||clock.cutoff::text)::uuid AS run_id,
   md5('isl-engine-v01-signal|'||m.model_code||'|'||clock.cutoff::text)::uuid AS signal_id,
   missing.missing_series,paper.contributions_pln,paper.booked_fees,paper.prior_fills,
   prices_summary.eligible_rows,source_manifest.rows AS sources,
   jsonb_build_object(
      'model_code',m.model_code,'model_version',m.version_no,
      'cutoff_utc',clock.cutoff,'model_rules',m.rules,
      'eligible_market_rows',prices_summary.eligible_rows,
      'latest_market_references',source_manifest.rows,
      'missing_total_return_series',missing.missing_series,
      'virtual_contributions_pln',paper.contributions_pln,
      'booked_fees_pln',paper.booked_fees,'historical_paper_fills',paper.prior_fills
   ) AS evidence
  FROM models m
  JOIN missing USING(model_code)
  JOIN paper USING(model_code)
  CROSS JOIN clock CROSS JOIN prices_summary CROSS JOIN source_manifest
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
        jsonb_build_object('engine','working-engine-v01','paper_only',true,
          'no_execution_api',true,'model_rules',p.rules,
          'source_availability','ingested_at_and_observed_for_not_after_cutoff',
          'no_historical_vintage_certification',true),
        jsonb_build_object('verdict',p.verdict,
          'missing_series',p.missing_series,
          'eligible_market_rows',p.eligible_rows,
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
        jsonb_build_object('engine','working-engine-v01',
          'run_id',p.run_id::text,'input_sha256',p.input_hash,
          'missing_series',p.missing_series,'new_paper_events',0),
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
        'Working Engine v0.1 completed research cycle without financial execution',
        jsonb_build_object('model_code',p.model_code,
           'input_sha256',p.input_hash,'cutoff',p.cutoff,
           'signal_verdict',p.verdict,'new_paper_events',0,
           'test_branch_only',true)
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
       0 AS paper_events_created,0 AS financial_operations
FROM sealed p
LEFT JOIN preexisting e USING(run_id)
LEFT JOIN inserted_runs r USING(run_id)
ORDER BY p.model_code;
