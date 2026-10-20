# Investment Strategy Lab — real-source hourly paper research, frozen Aug–Sep 2026

**Research status:** retrospective **educational** portfolio accounting, NOT investable execution, verified original publication-time PIT, actual achievable profits or a trade recommendation. Five fixed policies were already implemented and frozen on merged PR #53; this PR adds NO policy parameter optimization or real order functions.

## Scope and source authority

- Exactly **2026-08-01 00:00 UTC – 2026-10-01 00:00 UTC**, end-exclusive: 61 calendar days, **1,464 contiguous hourly observations per crypto pair**, 100 PLN virtual contribution per new calendar month, total 200 PLN for all five identical-policy budgets.
- Coinbase public no-auth `BTC-USD` and `ETH-USD` OHLCV: [official public candle endpoint](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/public/get-public-product-candles). **11 bounded HTTPS requests per pair**, each max 144h, strict source URL, UTC hourly alignment, OHLC shape/volume, no missing rows, independent RAW JSON and normalized canonical SHA per response. No private Coinbase data, API keys or trading capabilities.
- USD/PLN: [official NBP Table A historical USD mid rates](https://api.nbp.pl/api/exchangerates/rates/a/usd/2026-07-20/2026-09-30/?format=json), [NBP API manual](https://api.nbp.pl/). Current NBP archive returned **53 publication-date entries**. NBP's [published update-hours guidance](https://nbp.pl/statystyka-i-sprawozdawczosc/kursy/informacja-o-terminach-publikacji-kursow-walut/) describes daily Table A updates **11:45–12:15 Warsaw local time**. The API has `effectiveDate` but not historical publication SECOND. Thus at any hourly market bar the code permits a rate only **from 00:00 UTC on the FOLLOWING calendar day** after that `effectiveDate`. Weekends inherit the last rate subject to max 5-day staleness. This is a conservative assumption, **NOT verified historical raw FX price availability**. NBP official Table A mid-price is NOT executable bid/ask nor FX conversion cost.
- `source_vintage=RECONSTRUCTED_HISTORICAL_REFERENCE`. Underlying historical source snapshots were fetched in October 2026, so we cannot certify the prices that could be fetched on each original August/September trading hour or retrospective revisions. `historical_pit_certified=false`, `profitability_proven=false`.

## Independent original source and code evidence — first actual successful 61-day run

[GitHub Actions run #39504690604](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39504690604), PR #55 original source head `65a4d803879e684e6add6c1c4889fe611af6c4c0`: all three jobs **SUCCESS**: 321/321 offline Python tests, 3/3 disposable PostgreSQL 16 integration tests, and real public-source portfolio simulation job success. Main remained unchanged; no Neon, permission or schema writes. Detailed source receipts, per-chunk original SHA and full result JSON in log line `REAL_PAPER_STRATEGY_RESEARCH`.

Original source checksums in that CI:
- BTC 1,464 hourly canonical SHA-256 `913383da1c4a348f0124b71d1c6c58eba873c9d0d24f5eaf61678c2eff1d20dd`.
- ETH 1,464 hourly canonical SHA-256 `bec69ab4d03b6bc5bd47a9ba2f0b31f7fb907f41730f52365bd25523a6428ceb`.
- NBP original RAW JSON SHA-256 `aee3e66c5dc2b8fffcd7b01b1be62df6a20f5eba43822f146ab61a8c119cbe4c`; canonical SHA-256 `e4dbb044c336132780eca9687f8c32122814e58b642c3fdbf0689acb968db7d9`.
- Frozen baseline simulator input SHA `6b3080122b7baa13d54471feb4aa3f8cbcd5f6fbb30c381c460b5e21858831ed`.

**Assumed brokerage friction** (NOT actual customer fees/fills): 20 bps commission and 10 bps slippage **per trade side**, no shorting/leverage, next-hour OPEN assumed price, execution/FX rates are reference proxies, not realized trades. The starting contribution occurs at the first observed hour and the second at 2026-09-01 00:00 UTC, not exact real bank/broker transfer windows.

| Frozen policy | Contributions PLN | Final reference value PLN | Reference P&L PLN | Trades | Fees + assumed slippage PLN | Flow-adjusted max DD |
|---|---:|---:|---:|---:|---:|---:|
| equal_dca BTC+ETH | 200 | 253.02 | +53.02 | 4 | 0.60 | 6.02% |
| momentum | 200 | 119.90 | -80.10 | 302 | 104.64 | 47.32% |
| mean_reversion | 200 | 114.76 | -85.24 | 295 | 98.17 | 52.65% |
| risk_filter | 200 | 118.56 | -81.44 | 494 | 103.56 | 47.31% |
| ensemble | 200 | 118.00 | -82.00 | 577 | 119.41 | 47.04% |

**This is descriptive and specific to ONE historical window, frozen costs and simplistic OPEN price execution.** The dynamically responding policies can turn over a small virtual budget many times and incur disproportionate costs, so apparent market movements alone are not evidence of net advantage. Only 2 contributions and 61 days were observed, nowhere near the intended 3–5 year horizon. There is no independent untouched future holdout and no predictive alpha. The baseline won only within this single narrow retrospective experiment; it is not a recommended investment strategy.

## Additional cost sensitivity — not model/strategy parameter tuning

A following implementation revision repeats the **same fixed policy rules** on the same fetched source bytes, without refetching within that CI run, for three fee/slippage cases: `0/0`, `20/10`, `40/20` basis points. It is diagnostic accounting for friction, NOT retrospective selection of an optimized strategy. The 61-day real-source result for those cases is recorded in the later exact-head CI log. Results should remain `UNKNOWN` until that exact run completes.

## Executable reproducibility and fail-closed scope

```sh
python3 -m unittest discover -s tests -p 'test_hourly_real_paper_research.py' -v
python3 -m scripts.hourly_real_paper_research   # one-time public HTTPS GET only; no keys or accounts
```

- `scripts/hourly_real_paper_research.py` consumes real public API rates directly **in RAM** and feeds the existing pure simulator. No source prices, account data, positions, portfolio identifiers or secrets are committed to the repository, persisted to Neon or uploaded as artifacts.
- `tests/test_hourly_real_paper_research.py` uses **manufactured** JSON/FX fixtures to test publication-day lag, duplicate/missing source, FX stale/future/invalid, source identity, 2-month contribution schedule and one source for all fixed cost scenarios.
- `.github/workflows/hourly-real-paper-research-pr55.yml` is scoped to PR **#55** only, with `contents: read`, no `push`, no `workflow_dispatch`, no cron, no secrets. Tests include existing source/PIT constraints on **disposable** PostgreSQL; NO real Neon connection.
- A missing candle, time-gated USDPLN reference, source coverage or HTTP error causes `FAIL`; the script never fills with invented data or upgrades PIT.
- Original archived source hashes/capture timing and assumed execution costs do **not** certify exchange tradability, accessible historical signal timing or historical guaranteed profitability.
- User's prior M1/M2/M3 paper models remain `HOLD_NO_CHANGE`.

## Completion definition for this scoped PR

- [x] Real fixed 61-day BTC/ETH source successfully downloaded with separate UTC/hash per chunk.
- [x] NBP public USDPLN publication-date reference integrity checked; next-day eligibility assumption labeled.
- [x] First real paper-only five-policy retrospective comparison with contributions, costs and drawdown; no alpha claim.
- [x] 321 tests + 3 isolated integration + real source CI PASS for initial implementation.
- [ ] Latest exact-head CI for additionally requested **cost sensitivity** PASS.
- [ ] Review latest diff and either merge this research-only PR or document actual blocker.
