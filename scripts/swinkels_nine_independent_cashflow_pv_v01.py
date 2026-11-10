"""Independent cash-flow PV verification of nine original Swinkels bond variants.

Research-only, SHA-pinned original DataverseNL file. Does NOT parse the
publisher's OpenFormula. Computes remaining 9y11m nominal par-bond value from
a geometrically discounted fixed coupon and principal; adds one month accrued
interest. Uses stable log1p/expm1 for near-zero and negative yields.

This independently reproduces the workbook's mathematical *model* but does
not prove the price convention is executable or contemporaneously PIT
available. Outputs only aggregate residuals and historical statistics.
No fund operations, trading, persistent market-data exports or M1–M3 changes.
"""
from __future__ import annotations

import json
import math
import sys

from scripts.research_swinkels_original_source_probe_v01 import (
    PUBLISHER, SourceUnavailable, fetch,
)
from scripts.swinkels_formula_topology_probe_v01 import SOURCE_ID, SOURCE_SHA
from scripts.swinkels_nine_equation3_diagnostic_v01 import (
    SHEETS, MONTHS, SOURCE_WINDOW, extract_nine,
)
from scripts.swinkels_original_us_equation3_audit_v01 import (
    summarize_monthly_returns,
)

MONTHS_PER_YEAR = 12
COUPONS_PER_YEAR = 2
CONTRACT_YEARS = 10
REMAINING_YEARS = CONTRACT_YEARS - 1 / MONTHS_PER_YEAR
PERIOD_COUNT = COUPONS_PER_YEAR * REMAINING_YEARS
ROUNDING_TOLERANCE = 1e-10


def remaining_par_bond_monthly_return(previous_yield_points: float,
                                      current_yield_points: float) -> float:
    """Independent stable present-value of a remaining 9y11m par coupon bond.

    The old 10y par yield fixes the semiannual coupon amount. The new yield
    discounts coupon and principal with a fractional coupon period. One
    month's accrued interest is then added. Both input yields are in percentage
    points, as prescribed by the source formula's explicit 200 and 1200
    conversion constants.
    """
    if any(type(value) not in (int, float) or not math.isfinite(value)
           or value <= -100 or value >= 100
           for value in (previous_yield_points, current_yield_points)):
        raise SourceUnavailable("invalid independent bond-model yield")
    discount_rate_per_period = current_yield_points / (100 * COUPONS_PER_YEAR)
    fixed_coupon_per_period = previous_yield_points / (100 * COUPONS_PER_YEAR)
    if 1.0 + discount_rate_per_period <= 0:
        raise SourceUnavailable("invalid bond discounting base")

    log_discount_factor = -PERIOD_COUNT * math.log1p(discount_rate_per_period)
    principal_pv = math.exp(log_discount_factor)
    if abs(discount_rate_per_period) < 1e-10:
        # Continuous extension of geometric annuity PV at zero yield.
        rate = discount_rate_per_period
        count = PERIOD_COUNT
        annuity_factor = (
            count - count * (count + 1) * rate / 2
            + count * (count + 1) * (count + 2) * rate**2 / 6
        )
    else:
        annuity_factor = -math.expm1(log_discount_factor) / discount_rate_per_period

    coupon_present_value = fixed_coupon_per_period * annuity_factor
    accrued_interest = previous_yield_points / (100 * MONTHS_PER_YEAR)
    estimated_return = principal_pv + coupon_present_value + accrued_interest - 1
    if not math.isfinite(estimated_return):
        raise SourceUnavailable("nonfinite independent cash-flow bond return")
    return estimated_return


def reconcile_all_nine(raw: bytes) -> dict:
    group = extract_nine(raw)  # strict original ODS digest and source coverage
    if set(group) != set(SHEETS):
        raise SourceUnavailable("country variant scope mismatch")

    report = []
    for sheet in SHEETS:
        records = group[sheet]
        if set(records) != set(SOURCE_WINDOW):
            raise SourceUnavailable("incomplete independent research window")
        gaps = []
        historical = []
        for i, month in enumerate(MONTHS):
            previous = records[SOURCE_WINDOW[i]]
            current = records[month]
            model_result = remaining_par_bond_monthly_return(
                previous["yield_points"], current["yield_points"]
            )
            observed = current["return_fraction"]
            if not math.isfinite(observed) or observed <= -1:
                raise SourceUnavailable("invalid original source monthly return")
            historical.append(observed)
            gaps.append(abs(model_result - observed))
        max_abs = max(gaps)
        if max_abs > ROUNDING_TOLERANCE:
            raise SourceUnavailable("independent cash-flow model residual exceeds tolerance")
        report.append({
            "variant": sheet,
            "months": len(MONTHS),
            "max_abs_independent_cashflow_residual": f"{max_abs:.3e}",
            "independent_cashflow_reconciliation": "PASS",
            "historical_research_statistics": summarize_monthly_returns(historical),
        })
    return {
        "original_publisher_ods_sha256": SOURCE_SHA,
        "source_sha_verified": True,
        "window": "2020-01..2022-12",
        "variants_verified": len(report),
        "monthly_observations_verified": sum(s["months"] for s in report),
        "reference_model": "remaining_9y11m_par_bond_cashflow_pv_plus_one_month_accrual",
        "report": report,
        "economic_executability_certified": False,
        "historical_pit_certified": False,
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
        "financial_operations": 0,
    }


def main() -> None:
    raw = fetch(PUBLISHER + "/api/access/datafile/" + str(SOURCE_ID), 5_000_000)
    print("SWINKELS_NINE_INDEPENDENT_PV_RECONCILIATION=" +
          json.dumps(reconcile_all_nine(raw), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except SourceUnavailable as exc:
        print("SWINKELS_NINE_INDEPENDENT_PV_RECONCILIATION=BLOCKED: " + str(exc))
        sys.exit(2)
