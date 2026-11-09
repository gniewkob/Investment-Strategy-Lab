"""I4: one-way boundary from A1 backtest reports to C1 research decisions.

This intentionally NEVER produces a source manifest or a paper candidate.
A1 synthetic/reconstructed benchmark accounting is not original market data,
an independently verified source licence, a historical PIT certificate, or a
tradable quote. A report can only be acknowledged as HOLD_CASH. No network,
database, provider, broker, wallet, or trading actions.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re

from scripts.monthly_proxy_backtest_v04 import MODELS, ASSETS

SCHEMA = "ISL_A1_TO_C1_DECISION_FIREWALL_V01_001"
MAX_REPORT_BYTES = 4_000_000
HEX64 = re.compile(r"^[0-9a-f]{64}$")
RESEARCH_REASONS = (
    "BACKTEST_IS_NOT_ORIGINAL_SOURCE",
    "SOURCE_RIGHTS_NOT_INDEPENDENTLY_VERIFIED",
    "HISTORICAL_POINT_IN_TIME_NOT_CERTIFIED",
    "INDEX_LEVEL_IS_NOT_EXECUTABLE_QUOTE",
)
EXECUTION_ZEROS = (
    "real_orders", "paper_events_created", "database_connections", "database_writes"
)
COMMON = frozenset({
    "status", "input_sha256", "source_vintage",
    "historical_pit_certified", "real_orders",
    "paper_events_created", "database_connections", "database_writes", "results",
})
COMPLETE = COMMON | frozenset({
    "first_observed_month", "last_observed_month",
    "monthly_contribution_pln", "training_periods", "test_periods",
    "fee_bps_assumption", "slippage_bps_assumption", "accounting_basis",
    "monthly_reference_levels_are_not_executable_quotes",
    "investment_performance_proven", "parameters_optimized", "fx_model_needed",
    "cash_interest_assumed", "costs_are_scenarios_not_actual_broker_fees",
})
MISSING = COMMON | frozenset({
    "models", "missing_required_series", "performance_proven",
})
SHORT_HISTORY = COMMON | frozenset({
    "models", "available_months", "minimum_historical_months",
    "missing_required_series", "investment_performance_proven",
})
STATUS_FIELDS = {
    "SYNTHETIC_TEST_ONLY": COMPLETE,
    "CONDITIONAL_HISTORICAL_RECONSTRUCTION": COMPLETE,
    "NOT_RUN_INSUFFICIENT_DATA": MISSING,
    "NOT_RUN_INSUFFICIENT_HISTORY": SHORT_HISTORY,
}
MODEL_REPORT_FIELDS = frozenset({
    "model_code", "contributed_pln", "end_reference_value_pln",
    "net_reference_pnl_pln", "simple_contribution_roi_pct",
    "flow_adjusted_twr_pct", "in_sample_twr_pct", "out_of_sample_twr_pct",
    "flow_adjusted_max_drawdown_pct", "assumed_fees_pln",
    "assumed_slippage_pln", "hypothetical_rebalance_count",
    "hypothetical_turnover_pln", "cash_pln",
    "final_fractional_reference_units", "timeline",
    "difference_vs_M1_reference_pln",
})
TIMELINE_FIELDS = frozenset({
    "month", "decision_at", "segment", "signal",
    "virtual_contribution_pln", "portfolio_reference_value_pln",
    "cash_pln", "assumed_fee_pln", "assumed_slippage_pln",
    "hypothetical_weights",
})


class BacktestBoundaryError(ValueError):
    """Reject a malformed or attempted promotion of A1 backtest evidence."""


def _canonical_bytes(value: object) -> bytes:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise BacktestBoundaryError("A1 report must be bounded canonical JSON") from exc
    if len(raw) > MAX_REPORT_BYTES:
        raise BacktestBoundaryError("A1 report exceeds bounded review size")
    return raw


def _check_a1_report(report: object) -> bytes:
    if not isinstance(report, dict):
        raise BacktestBoundaryError("A1 report must be a JSON object")
    status = report.get("status")
    fields = STATUS_FIELDS.get(status) if isinstance(status, str) else None
    if fields is None or set(report) != fields:
        raise BacktestBoundaryError("unsupported A1 schema, status, or promotion fields")
    if (not isinstance(report["input_sha256"], str)
            or HEX64.fullmatch(report["input_sha256"]) is None):
        raise BacktestBoundaryError("A1 input checksum must be a SHA-256 string")
    vintage = report["source_vintage"]
    if vintage not in ("SYNTHETIC_OFFLINE_FIXTURE",
                       "HISTORICAL_RESEARCH_RECONSTRUCTION"):
        raise BacktestBoundaryError("unrecognised research source vintage")
    if ((status == "SYNTHETIC_TEST_ONLY")
            != (vintage == "SYNTHETIC_OFFLINE_FIXTURE")
            and status != "NOT_RUN_INSUFFICIENT_DATA"):
        raise BacktestBoundaryError("contradictory A1 status and vintage")
    if (status in ("CONDITIONAL_HISTORICAL_RECONSTRUCTION",
                   "NOT_RUN_INSUFFICIENT_HISTORY")
            and vintage != "HISTORICAL_RESEARCH_RECONSTRUCTION"):
        raise BacktestBoundaryError("historical reconstruction vintage required")
    if report["historical_pit_certified"] is not False:
        raise BacktestBoundaryError("backtest cannot certify historical PIT")
    flag = ("performance_proven" if status == "NOT_RUN_INSUFFICIENT_DATA"
            else "investment_performance_proven")
    if report[flag] is not False:
        raise BacktestBoundaryError("backtest cannot certify strategy performance")
    for field in EXECUTION_ZEROS:
        if type(report[field]) is not int or report[field] != 0:
            raise BacktestBoundaryError("backtest financial or database activity claimed")

    results = report["results"]
    if not isinstance(results, list):
        raise BacktestBoundaryError("A1 results must be a list")
    if status.startswith("NOT_RUN_"):
        if results or report["models"] != list(MODELS):
            raise BacktestBoundaryError("blocked backtest must have no result or model promotion")
    else:
        if (report["accounting_basis"] !=
                "NON_EXECUTABLE_FRACTIONAL_TOTAL_RETURN_INDEX_PROXY"
                or report["monthly_reference_levels_are_not_executable_quotes"] is not True
                or report["costs_are_scenarios_not_actual_broker_fees"] is not True
                or report["parameters_optimized"] is not False
                or report["fx_model_needed"] is not False
                or report["cash_interest_assumed"] != "0"):
            raise BacktestBoundaryError("A1 reference-only accounting contract violated")
        n = report["training_periods"]
        k = report["test_periods"]
        if (type(n) is not int or type(k) is not int
                or n < 4 or k < 4 or n + k > 360):
            raise BacktestBoundaryError("invalid synthetic research windows")
        if len(results) != len(MODELS) or any(
                not isinstance(r, dict) or set(r) != MODEL_REPORT_FIELDS
                for r in results):
            raise BacktestBoundaryError("unexpected model report or promotion fields")
        if [r["model_code"] for r in results] != list(MODELS):
            raise BacktestBoundaryError("A1 model report identities modified")
        for model in results:
            timeline = model["timeline"]
            if not isinstance(timeline, list) or len(timeline) != n + k:
                raise BacktestBoundaryError("incomplete model research timeline")
            if (not isinstance(model["final_fractional_reference_units"], dict)
                    or set(model["final_fractional_reference_units"]) != set(ASSETS)):
                raise BacktestBoundaryError("unexpected non-executable proxy units")
            for entry in timeline:
                if (not isinstance(entry, dict)
                        or set(entry) != TIMELINE_FIELDS
                        or not isinstance(entry["hypothetical_weights"], dict)
                        or set(entry["hypothetical_weights"]) != set(ASSETS)):
                    raise BacktestBoundaryError("invalid synthetic timeline schema")
    return _canonical_bytes(report)


def review_backtest(report: object) -> dict:
    """Validate A1 shape, then unconditionally deny promotion into C1."""
    raw = _check_a1_report(report)
    models = {
        model: {
            "status": "HOLD_CASH",
            "reason": "A1_BACKTEST_NOT_QUALIFIED_SOURCE",
            "virtual_target": {"CASH_PLN": "1"},
        }
        for model in MODELS
    }
    result = {
        "schema": SCHEMA,
        "status": "HOLD_CASH_BACKTEST_NOT_QUALIFIED_SOURCE",
        "input_kind": "A1_NON_EXECUTABLE_RESEARCH_REPORT",
        "source_vintage": report["source_vintage"],
        "backtest_research_status": report["status"],
        "backtest_input_sha256": report["input_sha256"],
        "backtest_report_sha256": sha256(raw).hexdigest(),
        "model_decisions": models,
        "paper_candidates": [],
        "missing_or_blocked_sources": list(ASSETS),
        "research_blockers": list(RESEARCH_REASONS),
        "source_manifest_created": False,
        "source_rights_independently_certified": False,
        "historical_point_in_time_certified": False,
        "historical_pit_certified": False,
        "investment_performance_proven": False,
        "real_order_authorized": False,
        "integration_to_main_authorized": False,
        "orders_sent": 0,
        "paper_fills": 0,
        "financial_operations": 0,
        "database_writes": 0,
    }
    result["boundary_receipt_sha256"] = sha256(_canonical_bytes(result)).hexdigest()
    return result
