# Opportunity Radar — paired benchmark and validation protocol (PL)

**Status:** historical educational research, never a trade, allocation or financial performance claim. Zero Neon writes, no brokerage/exchange access, no schedule.

## What the last verified historical report actually proves

[Manual STAGING run #39245012461](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39245012461) analyzed 3,711 retrospective reference quotes, eight eligible daily series, 47 non-overlapping anomaly events (15 overlapping excluded), without proving original historical publication dates.

The research module compares the future five-observation-bar move after a detected historical anomaly with two signs observed on **the same event date**:
- the standardized deviation sign of a one-bar change (20-bar past-only z-score);
- a trivial sign-persistence rule based on the most recent one-bar price return.

All eight previously reported series showed **0 percentage points improvement** of radar-direction agreement over that last-bar sign rule on the matched event dates. This is a descriptive observation, not proof of equivalence or the absence/presence of predictive skill. The two methods are mechanically related.

Legacy source label stays UNVERIFIED_HISTORICAL_PUBLICATION. Historical EIA/crypto spot references must not be treated as PLN investable total-return instruments. WTI misses 35 official dates on staging, and authentic source records for historical BTC/ETH divergences remain unconfirmed.

## Offline paired research diagnostic

Run on the metadata file from the already completed educational pipeline:

    python -m scripts.paired_research_evidence --robustness-json /local/nonoverlap_validation.json

The new offline script consumes only descriptive event outcomes and prints an aggregate JSON: both methods correct, neither correct, radar-only correct, naive-only correct, sample size and signed percentage-point difference. It never reads or exports prices or account data, and never opens a network/database connection.

Mandatory statuses: PAIRED_BASELINE_DESCRIPTIVE_ONLY, NO_PREDICTIVE_ADVANTAGE_OR_EQUIVALENCE_CLAIM, point_in_time_certified=false, portfolio_change_authorized=false, real_orders=0.

The existing robustness artifact deliberately includes at most 12 events per series for display. If a series had MORE than 12 full events, the new tool refuses to compute a full-population comparison from a truncated tail. Fail closed also on mismatched totals, changed research source flag/fingerprint, forged hit counts or fictional source verification, duplicate/naive dates and differing outcome horizons.

No probability, confidence bound, p-value or apparently large past percentage is presented as an investable edge; the sample is sparse, serially dependent, selected after seeing historical outcomes and has non-verified original source vintages.

## Prospective evaluation — preregister before seeing future outcomes

This is a research protocol to be implemented and independently reviewed in a later phase; it is NOT activated by this PR.

1. First obtain dated official publication/retrieval records and explicit per-observation provenance. Observation date alone does not prove an original historical price was available at that time. Do not backdate sources.
2. Freeze the full experiment in advance: instruments, source eligibility, lookback=20, threshold |z|>=2.5, five-future-bar horizon, non-overlap selection, calendar, anomaly exclusions, treatment of corrections and missing observations, frozen Git commit and data fingerprints.
3. Begin a genuinely untouched forward period. The already-explored 2024–2026 historical event outcomes CANNOT become a confirmatory holdout retroactively.
4. Evaluate on identical dates against naive last-bar sign, no-signal reference and a separate predeclared calendar/volatility-matched control. Compare discordant paired outcomes as well as directional agreement; do not confuse independent-grid and matched-event rates.
5. Predetermine sample adequacy, blockwise uncertainty for serial dependence, and multiple-hypothesis corrections across series/horizons, then test regimes and adverse samples without post-hoc redesign.
6. Fail/hold for source gaps or revisions, missing point-in-time evidence, less-than-required full paired events, data leakage, instability or no incremental advantage above naive controls. Stop at INSUFFICIENT_EVIDENCE and HOLD_NO_CHANGE; no financial action.
7. Portfolio-level educational experiments are out of scope until original M1/M2/M3 have genuine PLN total-return data, FX, costs, timing and independent model review.

Current result remains: **retrospective descriptive questions only**. No claim of forecast validity, causal macro relationship, actual alpha, legal tradability or portfolio change.

Data issues: [#2](https://github.com/gniewkob/Investment-Strategy-Lab/issues/2), [#22](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22). Completed safety fixes #21 and #23 stay closed.
