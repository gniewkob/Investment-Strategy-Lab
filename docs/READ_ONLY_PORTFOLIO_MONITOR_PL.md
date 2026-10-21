# Investment Strategy Lab — read-only market & portfolio risk monitor

**Purpose.** An on-demand monitoring service, NOT a trading engine: show fresh observed BTC/ETH/ATOM hourly-market conditions, a conservatively time-eligible official NBP USD/PLN midpoint, and, optionally, a **private** supplied Coinbase read-only portfolio snapshot. Observe risk concentrations and staking/availability distinctions. No buy/sell messages, orders, account authentication, real-money portfolio alterations, scheduled background jobs, Neon writes, or changed M1–M3.

## Actual execution paths

**A. Public market intelligence — no account information, works in GitHub Actions.**

```bash
python3 -m scripts.read_only_portfolio_monitor --format markdown
python3 -m scripts.read_only_portfolio_monitor --format json
```

On `main`, trigger the manual-only workflow **Read-only Market and Portfolio Intelligence** via Actions > Run workflow. It has `contents: read`, does **not** use secrets, does **not** consume portfolio data, and contains no `schedule` or account-specific inputs. Results appear only in the job log, with UTC timestamp. It makes **three** public HTTPS reads, one 72-hour OHLCV request for each of `BTC-USD`, `ETH-USD` and `ATOM-USD`, and **one** official NBP Table A USD midpoint request. Any HTTP failure or incomplete 72-hour data fails closed; **Coinbase HTTP 429 is possible**, so the workflow is intentionally NOT scheduled.

**B. Optional private, manually provided portfolio snapshot — local only.**

```bash
python3 -m scripts.read_only_portfolio_monitor --portfolio-file /path/to/private-portfolio.json --format markdown
```

The JSON document must contain `source="USER_SUPPLIED_READ_ONLY_COINBASE_CAPTURE"`, `captured_at` (original UTC extraction time), `portfolio_balances.total_balance` in USD and `spot_positions` with USD valuations, matching the selected **read-only** Coinbase portfolio response schema. Collect that snapshot through an already authorized private session, **not in public GitHub PR/issues/actions**, and never include OAuth tokens, account UUIDs, addresses, names, emails or other account identifiers in this file. The CLI does NOT connect to the user's Coinbase account. It never saves the private file; stdout remains local. It rejects future dates and snapshots older than 30 days; over 24 hours old is explicitly flagged as potentially stale.

A private, *synthetic* test-only example (entirely fabricated):

```json
{
  "source": "SYNTHETIC_TEST_ONLY",
  "captured_at": "2026-10-21T02:00:00Z",
  "portfolio_balances": {"total_balance": {"currency": "USD", "value": "100"}},
  "spot_positions": [
    {"asset": "ETH", "total_balance_fiat": 80, "account_type": "ACCOUNT_TYPE_STAKED_FUNDS"},
    {"asset": "ATOM", "total_balance_fiat": 20, "account_type": "ACCOUNT_TYPE_STAKED_FUNDS"}
  ]
}
```

To monitor **real** holdings use the `USER_SUPPLIED_READ_ONLY_COINBASE_CAPTURE` flag and genuine captured values; do not relabel the synthetic example as real. The report independently checks that position-level USD totals reconcile to the balance (0.5% / USD 0.05 tolerance), aggregates staked and liquid *categories*, identifies largest asset share and signals portfolio-capture staleness. **Staked assets count in total holdings but are not assumed tradable.** `total_balance_fiat` is Coinbase's approximate value and not guaranteed realizable sale proceeds; `available_to_trade_fiat` absence is **UNKNOWN liquidity**, not zero or fully liquid. An explicitly zero/unvalued fiat account placeholder is tolerated; an actual unvalued holding fails closed. Only BTC/ETH/ATOM are watched for market candles, but the optional portfolio snapshot accepts other source-valued assets and never silently discards them.

## Source timing and controls

- Coinbase public `/api/v3/brokerage/market/products/{product_id}/candles`, requested `ONE_HOUR`, `start` at 72 hours before the last **finished** UTC hour, `end` exclusive; duplicate/missing/malformed bars rejected. Last quoted price = **closed bar** (not live bid/ask or executable fill). Change is prior-24-hour close to last close; observed short-horizon volatility is calculated from last 24 hourly close-to-close returns; not a forecast.
- NBP historical USD Table A, 35 calendar days of archived `effectiveDate` records; reference eligible only at **00:00 UTC of next calendar date**, at most five days old. This is a conservative timing assumption, **not an independently verified historical publication clock** or an executable FX quote.
- Public market data available on request; no regular unattended checks promised. One-shot public monitoring alone cannot infer real account exposure, real-money gains, available balance, executable transaction prices or future returns.
- `risk_flags` only classify staking share, largest-asset concentration, stale account capture, and unknown liquid balances, without investment signals.
- Input fingerprints and source SHA-256 for market/FX support reproducibility of observed requests, but later retrieval may differ or be rate-limited; a single successful source run does not establish high availability.
- **No investment alpha certification, trade authorization, liquidity guarantee, price prediction or financial recommendation.**

## Acceptance criteria

1. Offline source parsing, SHA, last-finished-hour time enforcement, 24-hour movement, NBP publication-day lag, missing/stale/future data and account-position reconciliation all tested on explicitly synthetic fixtures.
2. Real read-only public endpoint market report (BTC, ETH, ATOM, NBP) executes on GitHub Actions PR and, once merged, by manual workflow dispatch with no secrets or private data.
3. No trading endpoints, account auth, production writes or schedules. No real account holdings in GitHub workflow/artifact.
4. Optional genuine user-supplied, private snapshot displays correct concentration/staking, without inferring availability to trade from total holdings. A live Coinbase read-only connector view from this chat is **not** an automated adapter to the GitHub workflow.
5. Acceptance requires exact-head green CI; **do not call the new service deployed/scheduled unless explicitly verified.**

## Known boundaries

The system is on-demand, not a 24/7 service. Portfolio holdings are accepted only as local read-only snapshots, so recurring automatic account refresh requires a **separately designed private authorized integration**, which is not activated here. Market prices do not represent guaranteed executable fills, and the NBP rate does not cover exchange conversion spread. No actual trading or staking unlocks.
