# Opportunity Radar v0.1 — retrospective research only

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
