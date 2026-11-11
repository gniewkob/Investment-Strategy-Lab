# Working Engine v0.4 — monthly benchmark-proxy backtesting

**Status (2026-11-06): ALGORITHM PASS; REAL M1/M2/M3 HISTORICAL PERFORMANCE NOT_RUN.**
The project has **no production environment**. Neon main is a private
research laboratory, not a brokerage account. This development increment
does not change Neon data, automation schedules, paper events or funds.

## What is implemented

- scripts/monthly_proxy_backtest_v04.py: deterministic pure Python
  three-model comparison with a common explicit month-end source calendar,
  100 PLN hypothetical monthly contributions PER ALTERNATIVE MODEL,
  fractional NON-EXECUTABLE index units, estimated commission/slippage,
  zero-interest residual cash, month-by-month hypothetical positions,
  nominal reference value/P&L, cashflow-neutral TWR, IS/OOS TWR and
  flow-adjusted maximum drawdown.
- db/monthly_backtest_v04_readiness_READONLY.sql: independent read-only
  inventory of required monthly PLN total-return source families and
  chronology, no orders and no writes to Neon.
- tests/test_monthly_proxy_backtest_v04.py: synthetic and explicit
  non-certified historical-reconstruction cases, strict input validation,
  no-lookahead, cash/leverage bounds, fee/slippage impact, deterministic
  SHA-256, model weights and M3 signal; includes a FIVE-YEAR synthetic
  schedule with 60 separate 100 PLN hypothetical contributions.
- tests/integration/test_monthly_backtest_v04_readiness.py:
  disposable PostgreSQL exercises real SQL, source absence, PRICE_ONLY
  and wrong FX currency exclusion, <36 months, future ingestion exclusion,
  gapped 36-month history and nontradable-source classification.

### Predefined comparison strategies

- M1_GLOBAL_EQ: 100% GLOBAL_EQUITY_TR_PLN.
- M2_DIVERSIFIED: 60% GLOBAL_EQUITY_TR_PLN,
  30% PL_BONDS_TR_PLN, 10% GOLD_TR_PLN.
- M3_TACTICAL: starts in cash while four monthly index levels are
  unavailable; then uses the cumulative global-equity index change over
  the most recent three fully closed monthly periods (last / three
  months prior). Positive -> 60/30/10 weights, nonpositive ->
  30% global equities, 30% Polish bonds, 10% gold, 30% virtual cash.
  This rule and its zero threshold are predeclared, not optimized
  against hindsight. No leverage or short selling is permitted.

The training/test split is specified in advance and used only for
separate reported time-weighted return segments; there is no tuning
step. Even with historical series it would NOT constitute independent
proof of alpha or future profitability.

### Financial interpretation of a result

This is **benchmark-proxy accounting**, NOT a fill simulation. A
month-end index level can only become known after the end of that month.
v0.4 applies a hypothetical allocation at that published reference
level for accounting; an order placed after publication could never
be guaranteed to execute at the historical month's close. The output
therefore uses the literal label:

NON_EXECUTABLE_FRACTIONAL_TOTAL_RETURN_INDEX_PROXY.

The backtest measures what a mathematical index-unit allocation would
do under the stated cost and cash assumptions, NOT actual obtainable
fund returns. Each strategy is evaluated with the SAME alternative
100 PLN monthly budget; the three virtual budgets are not three
actual deposits. Transaction costs are hypothetical bps, not current
or historical broker quotes. Fund NAVs may already include embedded
management expenses; don't blindly deduct those again. CPI,
dividends not contained in a source's explicit total-return basis,
tax, real dealing price, brokerage restrictions, FX settlement and
risk-free cash interest are not calculated here.

### Input contract

Run:

    python -m scripts.monthly_proxy_backtest_v04 --input /path/to/research-manifest.json

The JSON object must include:
- mode: EDUCATIONAL_RESEARCH_ONLY
- source_vintage: SYNTHETIC_OFFLINE_FIXTURE or
  HISTORICAL_RESEARCH_RECONSTRUCTION
- historical_pit_certified: false (a manifest cannot certify itself)
- monthly_contribution_pln: "100", fee_bps and slippage_bps:
  explicit nonnegative string scenario assumptions, bounded at 200 each
- training_periods: fixed integer; both train and test need at
  least four months
- periods: ordered consecutive month YYYY-MM entries with decision_at
  an explicit UTC timestamp in the immediately FOLLOWING month
- series: exactly GLOBAL_EQUITY_TR_PLN, PL_BONDS_TR_PLN,
  GOLD_TR_PLN. Each has source_url (HTTPS), source_sha256,
  quote_currency=PLN, return_basis=TOTAL_RETURN,
  instrument_kind=NON_EXECUTABLE_BENCHMARK and rows matching periods.
- each row: month, observed_for (late-month calendar date),
  first_usable_at (UTC timestamp after observation and by decision),
  level_pln (strict positive finite decimal string).

For historical comparisons the test requires **at least 36
consecutive months**, a calendar without missing periods and no future
dates. A shorter history returns NOT_RUN_INSUFFICIENT_HISTORY,
not a performance number. SYNTHETIC_OFFLINE_FIXTURE permits shorter
algorithm tests, but these are labelled SYNTHETIC_TEST_ONLY.
A real-data reconstruction is always explicitly labelled
CONDITIONAL_HISTORICAL_RECONSTRUCTION, historical_pit_certified=false,
investment_performance_proven=false. It does not claim the historical
timestamp, source licence or valuation basis independently certified.

When a required source is missing, output is
NOT_RUN_INSUFFICIENT_DATA with an explicit missing_required_series
array and results=[]. No invented gap fill, ETF index conversion,
purchase, sale, virtual paper-event append or account operation.

## Actual Neon main validation — NOT_RUN

Project red-lake-53043722, branch br-shy-voice-badzlf0x,
database investment_lab. The read-only SQL was executed against
the actual live private LAB on 2026-11-06.

| Required series | Instrument registered | Qualified months | Result |
|---|---|---:|---|
| GLOBAL_EQUITY_TR_PLN | No | 0 | NOT_RUN_SERIES_MISSING |
| PL_BONDS_TR_PLN | No | 0 | NOT_RUN_SERIES_MISSING |
| GOLD_TR_PLN | No | 0 | NOT_RUN_SERIES_MISSING |

The database DOES contain NBP FX, NBP gold, Coinbase BTC/ETH spot,
World Bank commodities and EIA energy reference prices. None
is equivalent to the three model-required monthly PLN total-return
series. They must not be relabelled or converted silently.

Source-readiness SQL separately requires monthly TOTAL_RETURN basis,
PLN currency, HTTPS provenance, observed and ingested before the
current evaluation, at least 36 DISTINCT month buckets and no
calendar gaps. **Even after all structural tests are met**, it
returns NEEDS_VINTAGE_AND_EXECUTION_EVIDENCE; it never certifies
the historical original release, tradable fill or broker fees.
All Neon read operations are read-only; no changes were made to
models, market observations, paper events or research history.

## How actual historical sources will be connected

Reuse (do not duplicate) PR #93 research intake modules and existing
official-source adapters. The engineering tasks are:

1. Global equity proxy: historical official NAV for the accumulating
   Vanguard FTSE All-World UCITS ETF can be a candidate in USD, BUT
   requires dated USDPLN conversion and documented treatment of the
   accumulating fund's NAV versus an executable ETF exchange price.
   This is not automatically GLOBAL_EQUITY_TR_PLN.
   Primary source:
   https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits-etf-usd-accumulating
2. Polish government bond benchmark: BondSpot TBSP.Index is a
   published total-return index including accrued interest and
   reinvestment of coupons, BUT is not a buyable security.
   Need original history, explicit matching instrument proxy and
   independent release evidence.
   Primary source:
   https://www.bondspot.pl/pressroom?ph_main_content_1_cmn_id=1309&ph_main_content_1_start=show
3. Gold: NBP publishes the calculated gold price in PLN/gram, which
   is reference PRICE_ONLY, NOT a documented investable total-return
   series. Construct a separately labelled and costed research proxy
   only after clarifying what gold exposure and source methodology
   are represented.
   Primary source: https://api.nbp.pl/
4. Capture historical timestamps/availability separately from today's
   retrieval time, raw byte SHA-256 and any source revision. A
   retrieved-in-2026 historical price is not proof it was available
   to a simulated trader on the old decision date.
5. Decide how actual execution prices, fees and slippage would be
   sourced for a later PAPER-FILL engine. Don't mark a total-return
   benchmark as a tradable ETF or bond.

These are SOURCE QUALITY and FINANCIAL MODELLING requirements, not
a bespoke permission registry blocking private educational work.
Observe any applicable provider usage terms without pretending
they prescribe an approval workflow.

## Acceptance evidence

PR #96 targets the branch of Draft PR #95 because v0.4 depends on
the v0.3 code, and is itself Draft. Neither branch is merged.
There are no changes to the active ChatGPT automation or to Neon
main writes. Dedicated tests are run by the existing inherited
Working Engine PostgreSQL CI in a completely disposable database.
The actual source inventory is read-only, as noted above.

**Acceptance decision:** monthly backtest ALGORITHM and fail-closed
SOURCE GATE = PASS when CI is green. Real historical M1–M3 performance
and any investment comparison = NOT_RUN / BLOCKED BY MISSING SERIES.
Natural repeated v0.3 cycles remain an independent unfinished
acceptance requirement; don't confuse them with offline backtesting.
