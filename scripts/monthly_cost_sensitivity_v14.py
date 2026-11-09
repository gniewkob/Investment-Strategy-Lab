"""v0.14 deterministic cost sensitivity for NON-EXECUTABLE M1/M2/M3 proxies.

Run the frozen v0.4 benchmark accounting on an explicit, predeclared
cost grid. This is neither a trading rule nor an opportunity ranking.
No real-world historical performance is inferred from synthetic fixtures.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

from scripts.monthly_proxy_backtest_v04 import (
    BacktestValidationError, MODELS, run_backtest,
)

SCHEMA = "ISL_MONTHLY_PROXY_COST_SENSITIVITY_V14_001"
GRID = (
    ("ZERO", "0", "0"),
    ("BASE_20_10", "20", "10"),
    ("HIGH_50_50", "50", "50"),
    ("STRESS_100_100", "100", "100"),
)
REQUIRED_STATUSES = {
    "SYNTHETIC_TEST_ONLY",
    "CONDITIONAL_HISTORICAL_RECONSTRUCTION",
    "NOT_RUN_INSUFFICIENT_HISTORY",
    "NOT_RUN_INSUFFICIENT_DATA",
}
UNEXECUTABLE = "NON_EXECUTABLE_FRACTIONAL_TOTAL_RETURN_INDEX_PROXY"


def _fingerprint(obj):
    return sha256(json.dumps(obj, sort_keys=True, ensure_ascii=True,
                             allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def analyze(payload):
    if not isinstance(payload, dict):
        raise BacktestValidationError("research manifest must be a JSON object")
    # Validate the supplied manifest BEFORE overwriting baseline cost fields.
    # This rejects altered statuses, false historical PIT or live execution.
    base = run_backtest(payload)
    if base["status"] not in REQUIRED_STATUSES:
        raise BacktestValidationError("unexpected underlying backtest status")
    outcomes = []
    for scenario, fee, slippage in GRID:
        candidate = deepcopy(payload)
        candidate["fee_bps"] = fee
        candidate["slippage_bps"] = slippage
        result = run_backtest(candidate)
        if result["status"] != base["status"]:
            raise BacktestValidationError("source gate changed across cost scenarios")
        models = {}
        if result["results"]:
            if (result["accounting_basis"] != UNEXECUTABLE or
                    set(m["model_code"] for m in result["results"]) != set(MODELS)):
                raise BacktestValidationError("non-executable model invariant violated")
            for item in result["results"]:
                models[item["model_code"]] = {
                    "end_reference_value_pln": item["end_reference_value_pln"],
                    "net_reference_pnl_pln": item["net_reference_pnl_pln"],
                    "flow_adjusted_twr_pct": item["flow_adjusted_twr_pct"],
                    "flow_adjusted_max_drawdown_pct": item["flow_adjusted_max_drawdown_pct"],
                    "out_of_sample_twr_pct": item["out_of_sample_twr_pct"],
                    "assumed_fees_pln": item["assumed_fees_pln"],
                    "assumed_slippage_pln": item["assumed_slippage_pln"],
                }
        outcomes.append({
            "scenario": scenario,
            "fee_bps_assumption": fee,
            "slippage_bps_assumption": slippage,
            "run_status": result["status"],
            "input_sha256": result["input_sha256"],
            "models": models,
        })
    have_data = bool(outcomes[0]["models"])
    changes = {}
    if have_data:
        best_case = outcomes[0]["models"]
        worst_case = outcomes[-1]["models"]
        for model in MODELS:
            low = Decimal(best_case[model]["end_reference_value_pln"])
            high = Decimal(worst_case[model]["end_reference_value_pln"])
            changes[model] = {
                "zero_cost_minus_stress_reference_pln": format(low - high, ".2f"),
                "stress_reference_not_higher_than_zero_cost": high <= low,
            }
    output = {
        "schema": SCHEMA,
        "status": ("SENSITIVITY_SYNTHETIC_TEST_ONLY" if
                   base["status"] == "SYNTHETIC_TEST_ONLY" else
                   "SENSITIVITY_CONDITIONAL_HISTORICAL_RECONSTRUCTION" if
                   base["status"] == "CONDITIONAL_HISTORICAL_RECONSTRUCTION" else
                   "NOT_RUN_SOURCE_OR_HISTORY_BLOCKED"),
        "underlying_status": base["status"],
        "source_manifest_sha256": _fingerprint(payload),
        "missing_required_series": base.get("missing_required_series", []),
        "available_months": base.get("available_months"),
        "scenario_count": len(GRID),
        "cost_scenarios_are_assumptions_not_broker_quotes": True,
        "benchmark_accounting_is_non_executable": True,
        "parameters_optimized": False,
        "historical_pit_certified": False,
        "investment_performance_proven": False,
        "statistical_edge_proven": False,
        "real_orders": 0,
        "paper_events_created": 0,
        "database_connections": 0,
        "database_writes": 0,
        "scenarios": outcomes,
        "model_cost_exposure": changes,
    }
    output["receipt_sha256"] = _fingerprint(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(json.loads(args.input.read_text(encoding="utf-8")))
    print("ISL_COST_SENSITIVITY_V14=" + json.dumps(result, sort_keys=True,
                                                 separators=(",", ":")))


if __name__ == "__main__":
    main()
