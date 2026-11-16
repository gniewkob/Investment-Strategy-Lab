# Paper scenario engine v0.1 (research only)

Run pure offline tests: `python3 -m unittest -v tests.test_paper_scenario_engine_v01`.

The deterministic `scripts.paper_scenario_engine_v01.run_scenario` accepts a contiguous sequence of monthly **explicit PLN scenario prices** with `month`, `price_pln`, and `available_month`. It uses a default 100 PLN monthly contribution, a cash-only comparator, fractional units, fixed PLN fees and proportional fees. Outputs monthly equity, cumulative fees, contributions and a terminal value. No HTTP, wallet, brokerage, database or real orders are used.

Inputs may be `SYNTHETIC` or `UNVERIFIED_EXTERNAL`. Both remain **unqualified for investment model use**. MF turnover, UKNF unit NAV, NBP spot references and Eurostat inflation/yields must **not** be silently converted into investable total-return prices. Historical price revisions and source first-publication timestamps are not certified.

**Important limit:** `available_month <= month` only rejects *monthly* future values. It does not establish intraday order-execution feasibility or historical PIT validity. Same-month close purchases are scenario arithmetic, not executable fill assumptions. This implementation is intentionally independent from M1/M2/M3, which remain HOLD_CASH. There is no order execution, asset transfer, model promotion or persistent data write.

Next integration must require a documented price schema, provenance, point-in-time availability at the chosen execution cutoff, currency and total-return/corporate-action treatment, with no fabricated observations. Cost assumptions are explicit and synthetic.

## Comparative research scenarios

`compare_scenarios(observations=..., strategies=[{"name":"zero fee","fee_fixed_pln":"0","fee_rate":"0"}, {"name":"charged","fee_fixed_pln":"1","fee_rate":"0.01"}])` uses **exactly the same monthly prices and contributions** for each named scenario. Cash is always included as a baseline. At most 12 strategies are accepted. Names must be distinct (case-insensitive), and invalid configuration or future-month prices fail closed.

The result is ranked by **terminal marked value**, not by annualized, time-weighted or risk-adjusted return. The ranking is a synthetic descriptive comparison; it is not a portfolio recommendation or evidence of predictive advantage. A fall in prices can rank cash highest. The engine does not derive prices or FX conversions from MF, UKNF, NBP or Eurostat contextual observations.

Offline regression command: `python3 -m unittest -v tests.test_paper_scenario_engine_v01`.
