# Opportunity Radar v0.2 — retrospective research with Data Quality Gate

## Data Quality & Evidence Gate v0.2 (offline, fail-closed)

Quality is now a **separate deterministic result** (`scripts/reference_data_quality.py`), included in `reference_data_quality.json` from both the educational evidence pipeline and the authorized manual historical bridge. It is fingerprint-bound to the exact retrospective radar snapshot.

- **Freshness heuristics, not publication verification:** daily price/reference series older than 10 calendar days, crypto daily older than 4 days, and monthly older than 75 days receive `STALE_DATA`. Lag is calculated against the snapshot export's timezone-aware `as_of`, **never the local wall clock or historic observation itself**. These conservative project-selected thresholds are screening conventions, not NIST/ISO or vendor mandates. Freshness **does not** prove actual publication chronology.
- **EIA peer-calendar coverage diagnostic:** when both WTI and Brent are present, the report counts Brent observation dates not present in WTI, including those later than WTI's last date. These are *reference-calendar mismatches*, not proof of EIA publication lag or exact WTI missing-release dates. If there are dates after WTI's final point, `PEER_COVERAGE_GAP` blocks research promotion.
- **Extreme cross-market divergence:** BTC/ETH matched-date relative-price divergence whose existing radar absolute z-score is at least 8 is marked `SOURCE_REVALIDATION_REQUIRED` for **both underlying series**. MAD-based robust z-score is independently reported as a diagnostic using lagged observations. Neither statistic verifies historical candle origin, explains an event, or establishes predictive alpha.
- **Research ledger enforcement:** quality warnings result in `DATA_QUALITY_BLOCKED` and `RESOLVE_DATA_QUALITY` priority, not `INVESTIGATE_RESEARCH_ONLY`. Source history can still be explored retrospectively without a portfolio consequence. Ledger rejects mismatched fingerprints, missing analyzed series, unknown classifications or false claims of verified vintages.
- **Same-date baseline:** independent-window diagnostics now show naive last-bar sign-persistence **on exactly the selected event dates** beside the event sign rate. The descriptive difference is not a causal advantage, confidence interval or investable benchmark.
- **Legacy gates unchanged:** `source_vintage=UNVERIFIED_HISTORICAL_PUBLICATION`; no automatic trade decisions, no writes, no API secrets, no schedules, no virtual allocations. `HOLD_NO_CHANGE` for M1/M2/M3.

### Verified 19.10.2026 staging findings behind this change

- Stored WTI references end on **2026-08-25**, while Brent ends on **2026-10-14**. There are 56 Brent dates absent from WTI's archive, including 35 after WTI's last point. The existing bridge does **not** repair source coverage, and this patch does not write price rows.
- BTC/ETH on 2026-08-19 shows approximately **−16.27** conventional z-score and **−18.32** robust MAD z-score for their daily relative USD price changes (20-bar prior reference). Anomaly arithmetic was checked against isolated staging, but original Coinbase records and publication vintages are **not independently authenticated**.
- The initial historical research report found 4 series for investigation based on sample screens, **not validated predictive performance**. v0.2 downgrades stale or extreme-anomaly source series pending evidence review. No historical source backfill or live staging run is part of this PR.

## Goal
Identify historical **questions worth investigating** and compare their subsequent reference-price changes with a no-flag baseline. This is an educational study, NOT an investment recommendation, order generator, live portfolio allocator or validated point-in-time backtest.

## Data contract
Input is a UTF-8 JSON object with:

- \`mode\`: \`RETROSPECTIVE_RESEARCH_ONLY\`
- \`source_vintage\`: \`UNVERIFIED_HISTORICAL_PUBLICATION\`
- \`as_of\`: timezone-aware ISO date/time of **snapshot/export**
- \`records\`: up to 15,000 rows with \`instrument_code\`, \`interval_code\` (\`1d\` or \`1mo\`), \`return_basis\` (\`PRICE_ONLY\` or \`FX_RATE\`), \`observed_for\`, \`ingested_at\`, \`close_price\`.

Historical records in \`investment_lab.price_observations\` were backfilled in October 2026. \`observed_for\` is when a price pertains to, NOT proof it was published that day. No backdating of provenance is allowed.

### Example (synthetic; not actual market prices)

\`\`\`json
{
  "mode": "RETROSPECTIVE_RESEARCH_ONLY",
  "source_vintage": "UNVERIFIED_HISTORICAL_PUBLICATION",
  "as_of": "2026-10-18T20:00:00Z",
  "records": [
    {
      "instrument_code": "BTC-USD",
      "interval_code": "1d",
      "return_basis": "PRICE_ONLY",
      "observed_for": "2026-01-02T00:00:00Z",
      "ingested_at": "2026-10-17T20:00:00Z",
      "close_price": "100"
    }
  ]
}
\`\`\`

The single row example passes source parsing but is **insufficient** for research statistics.

## Current implementation
- A lagged 20-bar baseline detects unusually large one-period price changes (|z| >= 2.5). Today's return is **never included** in its own baseline.
- Chronological 65/35 split: five subsequent observation-bar returns are evaluated only in the last 35% of the record, with 5 bars of forward history required. The split is descriptive; not validated out-of-sample predictive performance.
- Conditional shock mean is shown next to unconditional five-bar mean and 0% **nominal unchanged** reference. Overlapping forward windows, sparse signals, currency, proxy, costs and original publication vintages limit interpretation.
- BTC and ETH (both USD) are compared on **matched historical dates** only. A relative divergence is an inquiry, never evidence of arbitrage.
- Signals carry \`RETROSPECTIVELY_OBSERVED_NOT_ACTIONABLE\`; entire result \`INVESTIGATE_OR_OBSERVE_ONLY\`, \`virtual_portfolio_changes=0\`, \`real_orders=0\`.
- No default persistence. \`radar.json\` and \`report.md\` are local artifacts of the offline command.

\`\`\`sh
python -m unittest discover -s tests -p 'test_opportunity_radar.py' -v
python -m scripts.opportunity_radar --input /path/to/reviewed-snapshot.json --out-dir artifacts/opportunity-radar
\`\`\`

## Neon security boundary (not yet relaxed)
The established \`research-staging\` role \`isl_agent_staging_limited\` has **no SELECT on legacy \`price_observations\`**, by design. The offline radar neither bypasses that ACL nor connects to Neon. Do **not** add owner credentials to GitHub Actions and do not grant broad access just to run a scanner.

For a future staging-only integration, propose a **separate reviewed, read-only view or export of only**:
\`instrument_code, interval_code, return_basis, observed_for, ingested_at, close_price\`
with an exact allowlist, row cap, limited recipient and evidence audit. Credential changes and export publication require separate approval. The current CLI does not implement that integration.

## Roadmap and acceptance criteria
1. **Offline prototype (this PR):** reproducible warnings, instrument-specific anomalies, matched-currency comparison, holdout evidence, known limitations, no writes.
2. **Verified data bridge:** authorized narrow historic export, separate provenance/vintage labels, plus official historical sources for contemporary PIT.
3. **Historical research evaluation:** minimize overlapping observation windows; add proper train/validation/holdout with costs and benchmark confidence intervals before comparing paper allocations.
4. **Decision Intelligence:** separate deterministic assessment from LLM interpretation; attach evidence *for and against*, uncertainty, baseline \`HOLD_NO_CHANGE\` and journal a research-only classification.
5. **After external review:** consider regular read-only research reports. Never connect orders, broker accounts, or real-money allocation to this radar.

M1–M3 remain distinct **paper-only** simulations that need true PLN total-return inputs; legacy spot BTC/gold/EIA proxies must not be silently presented as verified substitutes.
