"""v0.21 cashflow-aware analytics for the v0.20 non-executable NAV reference.

Uses ONLY the complete, SHA-checked private Vanguard+NBP v0.4 artifact.
XIRR dates are source NAV dates, NOT plausible order dates; retrospective
same-close virtual purchases are impossible to guarantee. The drawdown is
of NAV/PLN reference levels (time-weighted price path), not portfolio P&L.
No market access, broker, wallet, network or database.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, localcontext
import json
from pathlib import Path

from scripts.conditional_m1_nav_diagnostic_v20 import evaluate_nav_reference, positive
from scripts.reference_archive_calendar_v04 import _digest

D = Decimal
SCHEMA = "ISL_CONDITIONAL_M1_NAV_ANALYTICS_V21_001"
SCENARIOS = (
    ("ZERO_0_0", "0", "0"),
    ("BASE_20_10", "20", "10"),
    ("HIGH_50_50", "50", "50"),
    ("STRESS_100_100", "100", "100"),
)


def _xirr(days, *, deposit, terminal):
    """Annualized XIRR of hypothetical outflows and terminal liquidation."""
    if len(days) != 60 or days[-1] <= days[0]:
        raise ValueError("invalid XIRR cashflow dates")
    initial = days[0]
    periods = [(d - initial).days / 365.25 for d in days]
    payment = float(deposit)
    terminal_f = float(terminal)
    if not (0 < payment <= 100000 and 0 < terminal_f < 1e10):
        raise ValueError("invalid XIRR cashflows")

    def npv(rate):
        growth = 1.0 + rate
        return sum(-payment / (growth ** exponent) for exponent in periods) + (
            terminal_f / (growth ** periods[-1]))

    low = -0.999
    high = 1.0
    while npv(high) > 0 and high < 1024:
        high = 2 * high + 1
    if npv(low) < 0 or npv(high) > 0:
        raise ValueError("XIRR cashflow rate is not bracketed")
    for _ in range(120):
        mid = (low + high) / 2.0
        if npv(mid) > 0:
            low = mid
        else:
            high = mid
    return D(str((low + high) / 2.0))


def _reference_max_drawdown(prices):
    peak = prices[0]
    worst = D("0")
    for price in prices:
        peak = max(peak, price)
        drawdown = price / peak - D("1")
        worst = min(worst, drawdown)
    return worst


def evaluate(artifact):
    # v0.20 is the already-tested strict input validator and reference
    # arithmetic. Reuse it rather than inventing a second source trust path.
    outcomes = []
    with localcontext() as ctx:
        ctx.prec = 38
        for name, fee, slippage in SCENARIOS:
            out = evaluate_nav_reference(artifact, fee_bps=fee,
                                         slippage_bps=slippage)
            prices = [
                positive(row["nav_pln_reference"], "NAV reference")
                for row in artifact["monthly"]
            ]
            dates = [date.fromisoformat(row["observed_for"])
                     for row in artifact["monthly"]]
            terminal = positive(out["nav_reference_net_final_pln"],
                                "terminal reference value")
            cash = positive(out["cash_reference_final_pln"], "cash baseline")
            rate = _xirr(dates, deposit=D("100"), terminal=terminal)
            cash_rate = _xirr(dates, deposit=D("100"), terminal=cash)
            drawdown = _reference_max_drawdown(prices)
            outcomes.append({
                "scenario": name,
                "fee_bps": fee,
                "slippage_bps": slippage,
                "cashflow_date_convention": "SOURCE_NAV_DATE_NOT_EXECUTABLE_ORDER_DATE",
                "hypothetical_net_final_pln": out["nav_reference_net_final_pln"],
                "hypothetical_difference_vs_cash_pln":
                    out["conditional_difference_vs_cash_pln"],
                "hypothetical_entry_frictions_pln":
                    out["hypothetical_cumulative_frictions_pln"],
                "hypothetical_xirr_annual_percent":
                    format((rate * D("100")).quantize(D("0.0001")), "f"),
                "zero_interest_cash_xirr_annual_percent":
                    format((cash_rate * D("100")).quantize(D("0.0001")), "f"),
                "nav_pln_reference_max_drawdown_percent":
                    format((drawdown * D("100")).quantize(D("0.0001")), "f"),
                "v20_result_sha256": out["research_receipt_sha256"],
            })
        base = outcomes[1]
        result = {
            "schema": SCHEMA,
            "status": "CONDITIONAL_NAV_ANALYTICS_RESEARCH_ONLY",
            "source_evidence_sha256": artifact["evidence_sha256"],
            "original_nav_file_sha256": artifact["nav_candidate_file_sha256"],
            "months": 60, "first_month": "2021-11", "last_month": "2026-10",
            "total_hypothetical_contributions_pln": "6000.00",
            "cash_reference_final_pln": "6000.00",
            "scenarios": outcomes,
            "base_case_scenario": base["scenario"],
            "xirr_method": "ACT_365_25_PERIODIC_CASHFLOWS_WITH_TERMINAL_LIQUIDATION",
            "drawdown_method": "NAV_PLN_MONTH_END_REFERENCE_LEVEL_PEAK_TO_TROUGH",
            "xirr_not_twr": True,
            "drawdown_not_cashflow_portfolio_drawdown": True,
            "historical_point_in_time_certified": False,
            "executable_fills_verified": False,
            "source_rights_independently_certified": False,
            "qualified_m1_model_backtest": False,
            "prospective_oos_performance_proven": False,
            "statistical_edge_or_alpha_proven": False,
            "orders_sent": 0, "paper_fills": 0,
            "database_writes": 0, "financial_operations": 0,
        }
        result["analytics_receipt_sha256"] = _digest(result)
        return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--nav-receipt", type=Path, required=True)
    args = p.parse_args()
    path = args.nav_receipt
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 3_000_000:
        raise ValueError("private bounded source receipt required")
    data = json.loads(path.read_text(encoding="utf-8"))
    output = evaluate(data)
    # Aggregates only. Never print NAV levels or month-by-month proprietary
    # observations; no source files uploaded to GitHub.
    print("ISL_CONDITIONAL_M1_ANALYTICS_V21=" +
          json.dumps(output, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
