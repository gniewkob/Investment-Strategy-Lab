# Investment Strategy Lab — Autonomous Delivery & Paper Tournament v1 (2026-10-20)

## 1. Mission, value and boundaries

**Mission:** build a reproducible educational investment-strategy laboratory that compares several **virtual portfolios** over daily/hourly data, learns which hypotheses are robust to costs and market periods, and records results with source provenance. The objective is reliable **evidence about strategies** under equal notional budget and risk constraints, not maximizing the number of simulated transactions. Historical success is not assured future profitability.

**Current user-directed scope:** BTC/ETH research, PLN accounting where an actually time-eligible USDPLN reference exists, virtual contributions **100 PLN/month** over 3–5 years, 1h and 1d variants. No real trading, live order placements, borrowing, leverage, platform deployment, change to existing simulated M1/M2/M3 or automatic schedule. This is an educational/experimental system, not trading advice.

Prior source research: 58 EIA STEO issues, 316 retrospective WTI/Brent pairs, 104 strict chronological comparisons. That informs provenance constraints but must not absorb the strategy-laboratory workstream. [STEO PR #52](https://github.com/gniewkob/Investment-Strategy-Lab/pull/52) remains a separate source-provenance task.

## 2. Inventory verified before implementation

- `main` at work start `fe986b23b47d080302b253eb87bbf7a10a93b0d4`; PR #52 open, separate PR #53 originally documentation-only.
- Existing scripts: `opportunity_radar.py`, `opportunity_research_pipeline.py`, `nonoverlap_validation.py`, `reference_data_quality.py`, `evidence_decision_ledger.py`. These are explanatory screens, not a multi-strategy portfolio simulator.
- Authenticated **read-only** Neon query confirmed BTC-USD and ETH-USD legacy `1d` reference series **381 observations each**, USDPLN_NBP `1d` **264 observations**, **zero `1h` rows in the inspected table**. Historical prices were backfilled in October 2026, so original point-in-time publication cannot be inferred.
- Connected Coinbase public read-only candle action for BTC-USD and ETH-USD produced **49 1h candles each** for a 48h window; exact UTC window boundary must be filtered. [Coinbase first-party public SDK](https://github.com/coinbase/coinbase-advanced-py/blob/master/coinbase/rest/public.py) also documents public, no-auth OHLCV endpoint. Neither source by itself supplies historically time-eligible intrahour FX.
- Current connected Coinbase tools include candle and market-data reads, but **no exposed push-notification inbox/history retrieval**. Phone notifications can be externally supplied hypothesis metadata; they do not replace raw market observations.

## 3. GREEN/AMBER/RED autonomy — applied operationally

| Category | Actions | Decision |
|---|---|---|
| **GREEN — autonomous** | Read authorized repo/data; offline research; public Coinbase price candle probes; write/repair code & tests on branch; run isolated CI; amend documentation/PR and OpenBrain; compare synthetic scenarios | Execute, fix failures, provide compact final evidence |
| **AMBER — risk assess, execute only if already authorized** | Merge code into default branch **after exact-head CI and review** if no production release/write access is involved; experiment with richer public data requiring no secrets; operator-controlled one-time public source job | Verify scope/reversibility/source provenance; never claim green for untested code |
| **RED — require separately authorized human action** | Real market transactions, account links/permissions or credential changes, Neon writes/migrations, external financial commitments, production deployment without approved mechanism, automatic background schedules, disabling source/risk gates | Do not execute; prepare reversible proposal only |

No self-assigned tier grants additional permissions.

## 4. Deliverables and acceptance

| Package | Deliverable | Objective acceptance gate | Current state |
|---|---|---|---|
| **D1** | `scripts/paper_strategy_tournament.py` pure offline 5-policy engine | Same monthly deposits; fixed parameters; hourly/daily; recorded fees, assumed slippage, PLN accounting; next-bar open decisions; no leverage, negative cash or real orders | IMPLEMENTED on PR #53; CI evidence must be checked at final head |
| **D2** | `tests/test_paper_strategy_tournament.py` and synthetic demonstration | Determinism, data SHA, future FX and missing bars rejection, no current/future close signal use, same budget, fee sensitivity, no false PIT labels | IMPLEMENTED; awaiting exact HEAD CI |
| **D3** | `.github/workflows/paper-strategy-tournament-pr53.yml` | Full Python tests; isolated disposable PostgreSQL tests; static side-effect exclusion; **no secret/no Neon** | IMPLEMENTED; awaiting exact HEAD CI |
| **D4** | Real public historical hourly plus historical as-of FX data bridge | Confirm hourly candle identity and coverage, FX observed/published-at timestamp; UTC alignment and missingness; signed/fingerprinted source receipts; 3–5yr data if available | **NOT BUILT** — avoid inventing market results |
| **D5** | Robust forward evaluation and prospective paper portfolio | Freeze strategies, compare independent chronological holdout and costs, display base currency total contributions, drawdown, turnover and fee sensitivity; repeated prospective receipts before strong claims | **NOT BUILT**; no profitable edge certified |
| **D6** | Automatic recurring reports and agent orchestrator | Safe schedule and alert delivery require separately requested authorization and approved execution environment | **NOT ENABLED** |

## 5. Frozen research policies and execution assumptions

`equal_dca` 50/50 monthly BTC/ETH benchmark; `momentum` stronger 24-bar (1h) or 20-bar (1d) backward trend if positive; `mean_reversion` weaker past performer if negative; `risk_filter` positive trend below a fixed realized volatility cap; `ensemble` fixed equal-vote mix. Any backtest outcome is conditional on these **predeclared rules**, not hyperparameter discovery.

Simulated order execution uses **the next bar's OPEN** (proxy fill), with explicit fee and slippage basis points, sells before buys, cash-only, no shorting. Trading occurs no more than once per bar per asset, and drift below 3 percentage points is ignored (monthly benchmark updates independently). Account value is marked to each bar's CLOSE, including assumed USDPLN reference. Historical base currency values are indicative: FX reference rates are **not executable spreads**, and a backfilled observation time is NOT a verified quote-publication time. Risk includes flow-adjusted drawdown and worst-bar return; simple contribution ROI is **not money-weighted IRR**.

Strict input: UTC strictly sequential hourly/daily bars; positive BTC/ETH OPEN/CLOSE and USDPLN; non-future non-stale `fx_asof` <= bar START (max five days); exact source label `SYNTHETIC_OFFLINE_FIXTURE` or `RECONSTRUCTED_HISTORICAL_REFERENCE`. Up to **60,000** rows support a 3–5-year hourly sample without promise of data availability. Bar source time, exact RAW source and publication PIT remain uncertified unless independently proven. No synthetic fixture may be relabeled real.

Outputs: input fingerprint SHA-256, metadata, per-policy contributed value, final value, simple gain vs cash-in, flow-adjusted drawdown, turnover, transactions, fees, slippage, cash, units, difference to equal DCA; `profitability_proven=false`, `historical_pit_certified=false`, `orders_sent=0`, `database_writes=0`, `M1/M2/M3=HOLD_NO_CHANGE`.

## 6. Reproducible operator commands (no keys or network)

```sh
python3 -m unittest discover -s tests -p 'test_paper_strategy_tournament.py' -v
python3 -m unittest discover -s tests -p 'test_paper_tournament_synthetic_demo.py' -v
python3 -m scripts.paper_tournament_synthetic_demo
# Only after verifying the supplied bar history/FX chronology:
python3 -m scripts.paper_strategy_tournament --input /path/to/reviewed_local_bars.json
```

The synthetic demonstration **manufactures every quote and its FX series**; any apparent profits are meaningless as evidence for BTC/ETH markets. It outputs no source file and does not connect to any service.

## 7. Acceptance and QA status conventions

- `PASS`: actual observed test/CI at the exact GitHub commit and scope.
- `FAIL`: failing test or source integrity; repair on PR before main merge.
- `UNKNOWN`: no actual source or sufficient time series; never infer alpha or genuine returns from a fabricated scenario.
- Keep `main` and PR #52 separate. Do not commit raw market source prices, API tokens, account data or transaction details.
- Exact-head CI result is recorded separately in the PR conversation and persistent OpenBrain once observed. Do **not** imply GitGuardian scan or a different-commit CI is equivalent to full CI.

## 8. Next autonomous packages

1. Finish PR #53 with exact-head full regression, syntax, test demo, review changed files, and clear result.
2. Build **read-only public hourly Coinbase BTC/ETH candle adapter** with bounded pagination and timestamp/coverage proofs, without permissions or orders. Test with a short one-shot public fetch first. FX source is a separate as-of quality gate; do not backdate NBP data or substitute live USDPLN as historical executable FX.
3. Freeze chronologically distinct evaluation windows and cost bands, with no iterative tuning on the held-out period. Preserve failed variants as negative results.
4. After verified history and independent holdout, support prospective *paper* tracking and compare long-run risk-adjusted outcomes. Recurrence remains disabled unless specifically authorized.

## 9. Human approval required

**No approval required for D1–D3 and follow-on read-only tests.** Approval or additional connection required for any scheduled pipeline, durable infrastructure/Neon writes, increased access, external commitments, or real-world orders. Those are not prerequisites for delivering the offline laboratory core.
