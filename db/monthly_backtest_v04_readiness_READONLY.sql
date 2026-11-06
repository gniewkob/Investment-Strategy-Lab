-- v0.4: read-only Neon source readiness. No strategy performance here.
-- 36 consecutive months and source vintage verification are separate gates.
WITH required(instrument_code,model_scope) AS (
 VALUES ('GLOBAL_EQUITY_TR_PLN','M1+M2+M3'),
        ('PL_BONDS_TR_PLN','M2+M3'),
        ('GOLD_TR_PLN','M2+M3')
),
structurally_qualified AS (
 SELECT p.instrument_code,p.observed_for
 FROM investment_lab.price_observations p
 JOIN investment_lab.instruments i USING(instrument_code)
 WHERE p.interval_code='1mo' AND p.return_basis='TOTAL_RETURN'
   AND i.quote_currency='PLN' AND p.close_price>0
   AND p.source_url LIKE 'https://%'
   AND p.observed_for<=now() AND p.ingested_at<=now()
),
present AS (
 SELECT r.instrument_code,r.model_scope,
        COUNT(q.instrument_code) AS monthly_qualified_rows,
        COUNT(DISTINCT to_char(q.observed_for AT TIME ZONE 'UTC','YYYY-MM'))
           AS distinct_qualified_months,
        MIN(q.observed_for) AS first_month,
        MAX(q.observed_for) AS last_month,
        bool_or(i.instrument_code IS NOT NULL) AS instrument_registered
 FROM required r
 LEFT JOIN investment_lab.instruments i ON i.instrument_code=r.instrument_code
 LEFT JOIN structurally_qualified q ON q.instrument_code=r.instrument_code
 GROUP BY r.instrument_code,r.model_scope
)
SELECT instrument_code,model_scope,instrument_registered,
       monthly_qualified_rows,distinct_qualified_months,
       first_month,last_month,
       CASE WHEN monthly_qualified_rows=0 THEN 'NOT_RUN_SERIES_MISSING'
            WHEN distinct_qualified_months<36 THEN 'NOT_RUN_INSUFFICIENT_MONTHS'
            WHEN (
                (EXTRACT(YEAR FROM last_month AT TIME ZONE 'UTC') -
                 EXTRACT(YEAR FROM first_month AT TIME ZONE 'UTC'))*12
                + EXTRACT(MONTH FROM last_month AT TIME ZONE 'UTC')
                - EXTRACT(MONTH FROM first_month AT TIME ZONE 'UTC') + 1
                 )<>distinct_qualified_months THEN 'NOT_RUN_GAPPED_MONTHS'
            ELSE 'NEEDS_VINTAGE_AND_EXECUTION_EVIDENCE'
       END AS model_research_readiness,
       'NEVER_INTERPRET_REFERENCE_INDEX_AS_EXECUTABLE_PRICE' AS execution_guard,
       0 AS paper_events_created,0 AS financial_operations
FROM present ORDER BY instrument_code;
