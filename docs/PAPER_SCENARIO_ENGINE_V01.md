# Paper scenario engine v0.1 (research only)

Run the end-to-end deterministic synthetic demo (60 fictional months, five fee
cases plus the zero-interest cash baseline):

```bash
python3 -m scripts.paper_scenario_engine_v01 --synthetic-demo --out-dir /tmp/isl-paper-demo
python3 -m unittest -v tests.test_paper_scenario_engine_v01
```

The CLI produces `comparison.json` and `report.md` without network requests,
account credentials, databases or broker access. Repeating the same input
generates identical output bytes. The report includes input SHA-256, period,
contributions, fees, terminal marked value and difference from the cash control.
The SHA is a reproducibility fingerprint, **not source authentication**.

To analyze externally supplied **unverified** monthly scenario levels, provide
strict JSON (all fields required; unknown fields are rejected):

```json
{
  "mode": "EDUCATIONAL_PAPER_ONLY",
  "source_class": "UNVERIFIED_EXTERNAL",
  "currency": "PLN",
  "price_basis": "EXPLICIT_MONTHLY_PLN_SCENARIO_PRICE",
  "monthly_contribution_pln": "100",
  "observations": [
    {"month": "2026-01", "available_month": "2026-01", "price_pln": "100"},
    {"month": "2026-02", "available_month": "2026-02", "price_pln": "101"}
  ],
  "strategies": [
    {"name": "no fee", "fee_fixed_pln": "0", "fee_rate": "0"},
    {"name": "cost 0.7pct", "fee_fixed_pln": "0", "fee_rate": "0.007"}
  ]
}
```

Run: `python3 -m scripts.paper_scenario_engine_v01 --input scenario.json --out-dir /tmp/isl-paper-input`.
The example values are **illustrative and invented**, not historical prices.
Numeric inputs must be finite decimal strings/integers (no floats/booleans),
within 32 significant decimal digits and adjusted decimal exponent -18 to 18;
out-of-range prices fail closed before division. JSON input is capped at 1 MB.
The source class may only be `SYNTHETIC` or `UNVERIFIED_EXTERNAL`.
`VERIFIED_MARKET_DATA` and price types such as `TOTAL_RETURN_INDEX` cannot be
self-declared through this interface. Reports always say `HOLD_CASH`, and do not
claim point-in-time certification or strategy admission.

The deterministic `scripts.paper_scenario_engine_v01.run_scenario` accepts a contiguous sequence of monthly **explicit PLN scenario prices** with `month`, `price_pln`, and `available_month`. It uses a default 100 PLN monthly contribution, a cash-only comparator, fractional units, fixed PLN fees and proportional fees. Outputs monthly equity, cumulative fees, contributions and a terminal value. No HTTP, wallet, brokerage, database or real orders are used.

Inputs may be `SYNTHETIC` or `UNVERIFIED_EXTERNAL`. Both remain **unqualified for investment model use**. MF turnover, UKNF unit NAV, NBP spot references and Eurostat inflation/yields must **not** be silently converted into investable total-return prices. Historical price revisions and source first-publication timestamps are not certified.

**Important limit:** `available_month <= month` only rejects *monthly* future values. It does not establish intraday order-execution feasibility or historical PIT validity. Same-month close purchases are scenario arithmetic, not executable fill assumptions. This implementation is intentionally independent from M1/M2/M3, which remain HOLD_CASH. There is no order execution, asset transfer, model promotion or persistent data write.

Next integration must require a documented price schema, provenance, point-in-time availability at the chosen execution cutoff, currency and total-return/corporate-action treatment, with no fabricated observations. Cost assumptions are explicit and synthetic.

## Comparative research scenarios

`compare_scenarios(observations=..., strategies=[{"name":"zero fee","fee_fixed_pln":"0","fee_rate":"0"}, {"name":"charged","fee_fixed_pln":"1","fee_rate":"0.01"}])` uses **exactly the same monthly prices and contributions** for each named scenario. Cash is always included as a baseline. At most 12 strategies are accepted. Names must be distinct (case-insensitive), and invalid configuration or future-month prices fail closed.

The result is ranked by **terminal marked value**, not by annualized, time-weighted or risk-adjusted return. The ranking is a synthetic descriptive comparison; it is not a portfolio recommendation or evidence of predictive advantage. A fall in prices can rank cash highest. The engine does not derive prices or FX conversions from MF, UKNF, NBP or Eurostat contextual observations.

The synthetic fee grid uses 0%, 0.2%, 0.7%, 1.5%, and a separate fixed 1 PLN
plus 0.7% per-contribution case. These are **assumed costs**, not actual broker
fees. The engine does not calculate annualized returns, time-weighted
performance, contribution-neutral drawdown, tax, or real fills.
