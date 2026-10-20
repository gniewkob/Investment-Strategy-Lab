# Investment Strategy Lab — Dynamic Hourly Research & Coinbase Notification Intake (2026-10-20)

**Status:** ARCHITECTURE / READ-ONLY SOURCE PROBE VERIFIED; **NO TRADING SIGNAL, NO PERFORMANCE CLAIM**.

## Objective

Study daily/hourly crypto market behavior and compare paper-only policies under identical data and cost assumptions, rather than attempt to maximize the number of trades. Research-only and simulation-only. Prior M1/M2/M3 remain `HOLD_NO_CHANGE`. No trades, no Coinbase orders, no Neon writes, no paid data, no secret/ACL changes, no recurring schedules, no model refitting on earlier STEO outcomes.

## Verified source capabilities (2026-10-20)

- Connected Coinbase capability `coinbase_products_candles` supports `granularity=1h` as well as other granularities and public product OHLCV history. Two actual read-only connector queries for `BTC-USD` and `ETH-USD`, requested `2026-10-14T00:00:00Z` to `2026-10-16T00:00:00Z` at `1h`, each returned **49 candles** and `truncated=false`. The extra boundary observation must be filtered by requested UTC interval; **do not classify 49 as 48 unique in-range hourly candles without normalization**.
- Existing Neon `investment_lab.price_observations` **read-only SELECT** confirms `BTC-USD` 381 daily rows, `ETH-USD` 381 daily rows, and `USDPLN_NBP` 264 daily rows, with no `1h` rows in that inspected table. Coinbase daily reference range 2025-10-01 to 2026-10-16. Source data were imported in October 2026; legacy observations do not certify original historical first-release PIT.
- Coinbase's [official mobile price alert guide](https://help.coinbase.com/en/coinbase/trading-and-funding/pricing-and-fees/what-are-price-alerts) documents watchlist/threshold-based **push/in-app/email price alerts** and says alerts are informational, not orders. [Official notifications overview](https://help.coinbase.com/en-gb/coinbase/managing-my-account/other/manage-notifications) covers market/asset/security account notifications.
- Connected Coinbase plugin tools were inspected; **no exposed notification-inbox or notification history retrieval action** was found. We have NOT ingested actual Coinbase mobile notifications, and no accessible first-party feed of user-level push events was verified. Do not infer that an app notification creates a programmatically readable event or has consistent timing/coverage.
- [Coinbase Advanced Trade WebSocket overview](https://docs.cdp.coinbase.com/advanced-trade/docs/ws-overview/) supports programmatic market-data streams; this is a different service from mobile app push notifications. New continuously running stream/subscription would need separate authorization and operational design, not enabled in this session.

## Two distinct data lanes

1. **Canonical market lane:** validated hourly OHLCV per asset from Coinbase for reproducible research. Capture the API request window, UTC timestamps, source product, canonical payload hash, observed bar completeness, price/volume sanity and retrieval timestamp. Never treat 1h candle OHLC averages as executable bid/ask fills. For historical simulations use next-bar execution assumptions, cost/slippage bands, and a holdout period not tuned on.
2. **Notification intelligence lane (OPTIONAL):** app push messages are **manual/external context**, at most event hypotheses. Require the full original alert text, product, event timestamp, received timestamp, source and independent OHLCV corroboration before attribution. Selective high-movement alerts can introduce event-selection bias and cannot replace complete market history. No phone notification interception or message forwarding configured.

## Next experimental engine v1 (NOT YET IMPLEMENTED OR VERIFIED)

- Paper policies: passive equal-weight BTC/ETH benchmark, prior-period momentum, short-term mean-reversion, volatility filter, and a frozen signal combination, all compared on the **same timestamps**.
- Independent frozen **cash-flow schedule** e.g. theoretical 100 PLN/month total per policy, no assumed unlimited funding, no leverage, no shorting, no real orders.
- Track contributions, equity/PLN FX reference, simulated turnover, fees, spread, assumed slippage, cash, end value, max drawdown, worst period, trade count and sensitivity.
- Chronological evaluation: indicator computed only from candles completed before the decision; next bar for hypothetical fill; no intrabar high/low fill assumptions; avoid lookahead, data snooping, instant zero-cost rebalance and using late-ingested history as previously knowable prices.
- Guardrails: no promotion to reliable profitability claim on a short sample, not even if one backtest strategy wins; compare walk-forward, different periods and cost bands, then prospective paper tracking.
- Portfolio M1–M3 remains unchanged even if a new experimental policy outperforms in simulated data. Default output `RESEARCH_ONLY`, `NO_TRADES`, `HOLD_NO_CHANGE`.

## Status and evidence standards

`HOURLY_SOURCE_AVAILABLE_AS_READ_ONLY_API=PASS` for the observed queries only; `HOUR_HISTORY_COMPLETE=UNKNOWN` beyond sampled window; `COINBASE_MOBILE_NOTIFICATIONS_PROGRAMMATIC_ACCESS=NOT_VERIFIED`; `FIRST_RELEASE_PIT=UNKNOWN`; `DYNAMIC_ALPHA_ESTABLISHED=false`; `STRATEGY_TOURNAMENT_PRODUCTION_ENGINE=NOT_BUILT`. Any untested demonstration numbers must be explicitly labeled as *illustrative*, not real backtest results.

This documentation-only note does not merge code, modify any production platform or start a recurring workflow.
