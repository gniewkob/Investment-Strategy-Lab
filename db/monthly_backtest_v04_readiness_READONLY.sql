-- v0.4: read-only, live-Neon readiness gate for M1/M2/M3.
-- An index name or a reference quote is NOT a tradable instrument.
-- Existence of rows alone NEVER proves source vintage or fill feasibility.
WITH required(instrument_code,model_scope) AS (
 VALUES
 ('GLOBAL_EQUITY_TR_PLN','M1+M2+M3'),
 ('PL_BONDS_TR_PLN','M2+M3'),
 ('GOLD_TR_PLN','M2+M3')
),
present AS (
 SELECT r.instrument_code,r.model_scope,
        count(p.instrument_code) FILTER (
          WHERE p.interval_code='1mo'
            AND p.return_basis='TOTAL_RETURN'
            AND i.quote_currency='PLN'
            AND p.close_price>0
            AND p.source_url LIKE 'https://%'
        ) AS monthly_qualified_rows,
        count(DISTINCT to_char(p.observed_for AT TIME ZONE 'UTC','YYYY-MM')) FILTER (
          WHERE p.interval_code='1mo'
            AND p.return_basis='TOTAL_RETURN'
            AND i.quote_currency='PLN'
            AND p.close_price>0
            AND p.source_url LIKE 'https://%'
        ) AS distinct_qualified_months,
        min(p.observed_for) FILTER (
          WHERE p.interval_code='1mo' AND p.return_basis='TOTAL_RETURN'
            AND i.quote_currency='PLN'
        ) AS first_month,
        max(p.observed_for) FILTER (
          WHERE p.interval_code='1mo' AND p.return_basis='TOTAL_RETURN'
            AND i.quote_currency='PLN'
        ) AS last_month,
        bool_or(i.instrument_code IS NOT NULL) AS instrument_registered
 FROM required r
 LEFT JOIN investment_lab.instruments i ON i.instrument_code=r.instrument_code
 LEFT JOIN investment_lab.price_observations p ON p.instrument_code=r.instrument_code
 GROUP BY r.instrument_code,r.model_scope
)
SELECT instrument_code,model_scope,instrument_registered,
       monthly_qualified_rows,distinct_qualified_months,
       first_month,last_month,
       CASE WHEN monthly_qualified_rows=0 THEN 'NOT_RUN_SERIES_MISSING'
            WHEN distinct_qualified_months<10 THEN 'NOT_RUN_INSUFFICIENT_MONTHS'
            ELSE 'NEEDS_VINTAGE_AND_EXECUTION_EVIDENCE'
       END AS model_research_readiness,
       'NEVER_INTERPRET_REFERENCE_INDEX_AS_EXECUTABLE_PRICE' AS execution_guard,
       0 AS paper_events_created,0 AS financial_operations
FROM present ORDER BY instrument_code;
