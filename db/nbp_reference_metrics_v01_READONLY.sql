-- Working Engine: read-only descriptive NBP reference evidence v1.
-- Reference FX mid-rates and calculated gold PLN/g are NOT executable assets
-- or total-return benchmarks. Zero portfolio actions and zero database writes.
-- One row per allowlisted series, always; empty/missing sources are explicit.
WITH clock AS (
  SELECT CASE
    WHEN now() >= ((date_trunc('day',now() AT TIME ZONE 'UTC') + interval '19 hours') AT TIME ZONE 'UTC')
      THEN (date_trunc('day',now() AT TIME ZONE 'UTC') + interval '19 hours') AT TIME ZONE 'UTC'
    ELSE (date_trunc('day',now() AT TIME ZONE 'UTC') - interval '5 hours') AT TIME ZONE 'UTC'
  END AS cutoff
),
allowed(instrument_code,source_code,return_basis) AS (
  VALUES ('USDPLN_NBP','nbp_rates','FX_RATE'),
         ('EURPLN_NBP','nbp_rates','FX_RATE'),
         ('GOLD_NBP_PLN_G','nbp_gold','PRICE_ONLY')
),
eligible AS (
 SELECT p.instrument_code,p.observed_for,p.ingested_at,p.close_price,p.source_url
 FROM investment_lab.price_observations p
 JOIN allowed a ON a.instrument_code=p.instrument_code
               AND a.source_code=p.source_code
               AND a.return_basis=p.return_basis
 CROSS JOIN clock c
 WHERE p.interval_code='1d' AND p.close_price>0
   AND p.observed_for<=c.cutoff AND p.ingested_at<=c.cutoff
),
ranked AS (
 SELECT instrument_code,observed_for,ingested_at,close_price,source_url,
        row_number() OVER (PARTITION BY instrument_code
                           ORDER BY observed_for DESC,ingested_at DESC) AS n
 FROM eligible
),
recent AS (SELECT * FROM ranked WHERE n<=21),
aggregate AS (
 SELECT a.instrument_code,a.source_code,a.return_basis,c.cutoff,
        count(r.n) AS observations_in_window,
        max(r.observed_for) FILTER (WHERE r.n=1) AS last_observed,
        max(r.ingested_at) FILTER (WHERE r.n=1) AS last_ingested,
        max(r.source_url) FILTER (WHERE r.n=1) AS latest_source_url,
        max(r.close_price) FILTER (WHERE r.n=1) AS latest_value,
        max(r.close_price) FILTER (WHERE r.n=6) AS value_five_observations_ago,
        max(r.close_price) FILTER (WHERE r.n=21) AS value_twenty_observations_ago,
        min(r.close_price) AS window_min_value,
        max(r.close_price) AS window_max_value,
        encode(sha256(convert_to(
          coalesce(jsonb_agg(jsonb_build_array(r.observed_for,r.ingested_at,r.close_price)
                             ORDER BY r.observed_for,r.ingested_at)
                   FILTER (WHERE r.n IS NOT NULL),'[]'::jsonb)::text,'UTF8')),'hex')
          AS eligible_window_sha256
 FROM allowed a CROSS JOIN clock c
 LEFT JOIN recent r ON r.instrument_code=a.instrument_code
 GROUP BY a.instrument_code,a.source_code,a.return_basis,c.cutoff
)
SELECT instrument_code,source_code,return_basis,cutoff,
       observations_in_window,last_observed,last_ingested,
       latest_value,
       CASE WHEN observations_in_window>=6
            THEN round(100*(latest_value/value_five_observations_ago-1),4)
            ELSE NULL END AS change_five_observations_pct,
       CASE WHEN observations_in_window>=21
            THEN round(100*(latest_value/value_twenty_observations_ago-1),4)
            ELSE NULL END AS change_twenty_observations_pct,
       CASE WHEN observations_in_window>=21
            THEN round(100*(window_max_value/window_min_value-1),4)
            ELSE NULL END AS range_twenty_observations_pct,
       CASE WHEN last_observed IS NULL THEN 'SOURCE_MISSING'
            WHEN cutoff::date-last_observed::date>7 THEN 'SOURCE_STALE'
            WHEN observations_in_window<21 THEN 'REFERENCE_WINDOW_SHORT'
            ELSE 'REFERENCE_RECENT' END AS reference_status,
       latest_source_url,eligible_window_sha256,
       'DESCRIPTIVE_REFERENCE_ONLY_NOT_TOTAL_RETURN' AS interpretation,
       0 AS paper_events_created,0 AS real_financial_operations
FROM aggregate
ORDER BY instrument_code;
