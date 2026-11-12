"""Bounded historical forecast-error diagnostic using original Swinkels data.

Educational retrospective analysis; NOT a strategy, backtest, source PIT
certificate, portfolio instruction or authorization for financial operations.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math

from scripts.research_swinkels_original_source_probe_v01 import (
    PUBLISHER, SourceUnavailable, fetch,
)
from scripts.swinkels_formula_topology_probe_v01 import (
    SOURCE_BYTES, SOURCE_ID, SOURCE_SHA,
)
from scripts.swinkels_original_us_equation3_audit_v01 import extract_original_us
from scripts.swinkels_nine_equation3_diagnostic_v01 import (
    MONTHS, SHEETS, extract_nine,
)
from scripts.swinkels_source_bound_stats_v01 import create_receipt

WARMUP = 12
TRAILING = 6
WINDOW = 36
SCHEMA = "ISL_SWINKELS_LAG_ONLY_FORECAST_ERROR_V01"


def _series(values):
    if not isinstance(values, (tuple, list)) or len(values) != WINDOW:
        raise SourceUnavailable("FORECAST_WINDOW_NOT_36_MONTHS")
    if any(type(x) not in (int, float) or not math.isfinite(x) or x <= -1
           for x in values):
        raise SourceUnavailable("FORECAST_RETURN_NOT_FINITE_OR_VALID")
    return tuple(float(x) for x in values)


def _predictions_before(values: tuple, index: int) -> tuple[float, float]:
    """Each prediction depends exclusively on months earlier than index."""
    if (not isinstance(values, tuple) or len(values) != WINDOW
            or type(index) is not int or not WARMUP <= index < WINDOW):
        raise SourceUnavailable("FORECAST_TARGET_INVALID")
    history = values[:index]
    return (math.fsum(history) / len(history),
            math.fsum(history[-TRAILING:]) / TRAILING)


def evaluate_lagged_error(values) -> dict:
    """Synthetic-testable paired MAE arithmetic; no source authentication."""
    series = _series(values)
    base_errors = []
    recent_errors = []
    improved = 0
    for index in range(WARMUP, WINDOW):
        baseline, candidate = _predictions_before(series, index)
        realized = series[index]
        base = abs(realized - baseline) * 10000
        recent = abs(realized - candidate) * 10000
        base_errors.append(base)
        recent_errors.append(recent)
        improved += recent < base
    base_mae = math.fsum(base_errors) / 24
    recent_mae = math.fsum(recent_errors) / 24
    if not math.isfinite(base_mae) or not math.isfinite(recent_mae):
        raise SourceUnavailable("FORECAST_AGGREGATE_NONFINITE")
    return {
        "initial_training_months": WARMUP,
        "evaluation_months": 24,
        "evaluation_first_month": "2021-01",
        "evaluation_last_month": "2022-12",
        "baseline": "EXPANDING_PRIOR_MONTH_MEAN",
        "candidate": "TRAILING_SIX_PRIOR_MONTH_MEAN",
        "error_units": "BPS_OF_MONTHLY_RETURN_PREDICTION_ERROR",
        "baseline_mae_bps": f"{base_mae:.4f}",
        "candidate_mae_bps": f"{recent_mae:.4f}",
        "paired_mae_improvement_bps": f"{base_mae-recent_mae:.4f}",
        "candidate_lower_error_months": improved,
        "confirmatory_holdout": False,
        "historical_pit_certified": False,
        "not_investment_performance": True,
    }


def source_bound_diagnostic(original: bytes) -> dict:
    """Refuse all input except the original SHA-pinned publisher ODS."""
    if (type(original) is not bytes or len(original) != SOURCE_BYTES
            or sha256(original).hexdigest() != SOURCE_SHA):
        raise SourceUnavailable("ORIGINAL_ODS_SHA_OR_SIZE_MISMATCH")
    proof = create_receipt(original)
    if (proof.get("original_sha256") != SOURCE_SHA
            or proof.get("monthly_observations") != 360
            or proof.get("source_variants") != 10
            or proof.get("financial_operations") != 0
            or proof.get("qualified_model_series") != []
            or proof.get("historical_point_in_time_certified") is not False
            or proof.get("dataset_2023_erasmus_v6_byte_equivalence_verified") is not False):
        raise SourceUnavailable("SOURCE_RECONCILIATION_INCOMPLETE")
    us = extract_original_us(original)
    other = extract_nine(original)
    if set(other) != set(SHEETS) or len(MONTHS) != WINDOW:
        raise SourceUnavailable("SOURCE_COUNTRY_OR_MONTH_SCOPE_MISMATCH")
    groups = [("Original_US_1962", [us[m]["return"] for m in MONTHS])]
    groups.extend(
        (name, [other[name][m]["return_fraction"] for m in MONTHS])
        for name in sorted(SHEETS)
    )
    if len(groups) != 10 or len({n for n, _ in groups}) != 10:
        raise SourceUnavailable("DUPLICATE_COUNTRY_VARIANTS")
    result = [{"variant": name, **evaluate_lagged_error(values)}
              for name, values in groups]
    receipt = {
        "schema": SCHEMA,
        "source": "Original DataverseNL CC BY 4.0, estimated foreign sovereign returns",
        "source_doi": "10.34894/YWT2IX",
        "source_file_id": SOURCE_ID,
        "original_sha256": SOURCE_SHA,
        "source_window": "2020-01..2022-12",
        "variant_count": 10,
        "evaluation_forecasts": 240,
        "lagged_error_statistics": result,
        "source_math_independently_reconciled": True,
        "erasmus_v6_byte_equivalence_verified": False,
        "historical_point_in_time_certified": False,
        "confirmatory_holdout": False,
        "non_polish_returns_ending_2022": True,
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
        "orders_sent": 0,
        "paper_events_created": 0,
        "database_writes": 0,
        "financial_operations": 0,
    }
    receipt["receipt_sha256"] = sha256(json.dumps(
        receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return receipt


def main() -> None:
    raw = fetch(PUBLISHER + "/api/access/datafile/" + str(SOURCE_ID), 5_000_000)
    print("SWINKELS_WALKFORWARD_RESEARCH_RECEIPT=" + json.dumps(
        source_bound_diagnostic(raw), sort_keys=True, separators=(",", ":")
    ))


if __name__ == "__main__":
    try:
        main()
    except SourceUnavailable as exc:
        print("SWINKELS_WALKFORWARD_RESEARCH_RECEIPT=BLOCKED:" + str(exc))
        raise SystemExit(2) from None
