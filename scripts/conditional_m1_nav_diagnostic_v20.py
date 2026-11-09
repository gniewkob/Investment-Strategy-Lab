"""v0.20 conditional historical Vanguard NAV/PLN vs cash *research diagnostic*.

Uses privately produced original-source NAV/FX intake receipt. This is a
retrospective non-executable fractional NAV-reference arithmetic experiment,
NOT an M1 qualification, financial order, actual execution, PIT backtest,
or prediction. No network, persistence or dependency on broker/Neon.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
import json
from pathlib import Path
import re

from scripts.reference_archive_calendar_v04 import _verify_digest, _digest

SCHEMA = "ISL_CONDITIONAL_NAV_M1_RESEARCH_V20_001"
EXPECTED_STATUS = "CANDIDATE_NAV_PLN_REFERENCE_READY_FOR_SOURCE_REVIEW"
M = re.compile(r"^20[0-9]{2}-(0[1-9]|1[0-2])$")
D = Decimal


def positive(value, label, *, zero=False):
    if isinstance(value, bool) or not isinstance(value, str) or value != value.strip():
        raise ValueError(label + ": decimal string required")
    try:
        x = D(value)
    except (InvalidOperation, ValueError) as e:
        raise ValueError(label + ": invalid decimal") from e
    if not x.is_finite() or x < 0 or (not zero and x == 0):
        raise ValueError(label + ": positive finite decimal required")
    return x


def _next_month(s):
    year, month = (int(x) for x in s.split("-"))
    return f"{year + (month == 12):04d}-{1 if month == 12 else month+1:02d}"


def evaluate_nav_reference(artifact, *, contribution="100", fee_bps="20",
                           slippage_bps="10"):
    if not isinstance(artifact, dict):
        raise ValueError("original candidate artifact object required")
    _verify_digest(artifact)
    if (artifact.get("status") != EXPECTED_STATUS
            or artifact.get("instrument_code") != "VANGUARD_ACC_NAV_REFERENCE_PLN"
            or artifact.get("usable_as_GLOBAL_EQUITY_TR_PLN") is not False
            or artifact.get("historical_pit_certified") is not False
            or artifact.get("executable_market_fill_price") is not False
            or artifact.get("fund_identity_authenticated_from_original_file") is not False
            or artifact.get("missing_exact_day_fx") != []
            or artifact.get("financial_operations") != 0
            or artifact.get("real_orders") != 0):
        raise ValueError("research-only unqualified NAV receipt required")
    rows = artifact.get("monthly")
    if (not isinstance(rows, list) or len(rows) != 60
            or artifact.get("months_requested") != 60
            or artifact.get("first_month") != "2021-11"
            or artifact.get("last_month") != "2026-10"):
        raise ValueError("exact 60-month source period required")
    payment = positive(contribution, "contribution")
    fee = positive(fee_bps, "fee", zero=True)
    slip = positive(slippage_bps, "slippage", zero=True)
    if payment != D("100") or fee > 200 or slip > 200:
        raise ValueError("100 PLN contribution and bounded costs required")
    last_month = None
    last_day = None
    last_price = None
    units = D("0")
    cash_baseline = D("0")
    cumulative_friction = D("0")
    gross_units = D("0")
    timeline = []
    with localcontext() as ctx:
        ctx.prec = 38
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                    "month", "observed_for", "nav_usd", "usdpln_nbp",
                    "nav_pln_reference", "nbp_source_url",
                    "nbp_response_sha256", "nbp_retrieved_at"}:
                raise ValueError("unexpected original monthly reference schema")
            month = row["month"]
            if not isinstance(month, str) or not M.fullmatch(month):
                raise ValueError("invalid source month")
            if last_month is not None and month != _next_month(last_month):
                raise ValueError("month gap or duplicate")
            try:
                day = date.fromisoformat(row["observed_for"])
            except (ValueError, TypeError) as exc:
                raise ValueError("invalid source date") from exc
            if day.strftime("%Y-%m") != month or day.day < 20:
                raise ValueError("NAV monthly observation date mismatch")
            if last_day is not None and day <= last_day:
                raise ValueError("out-of-order NAV")
            nav = positive(row["nav_usd"], "nav_usd")
            fx = positive(row["usdpln_nbp"], "usdpln_nbp")
            price = positive(row["nav_pln_reference"], "nav_pln_reference")
            if nav * fx != price:
                raise ValueError("NAV/FX source multiplication mismatch")
            if (not isinstance(row["nbp_source_url"], str) or
                    not row["nbp_source_url"].startswith("https://api.nbp.pl/api/")):
                raise ValueError("official NBP source URL required")
            if (not isinstance(row["nbp_response_sha256"], str) or
                    not re.fullmatch(r"[a-f0-9]{64}", row["nbp_response_sha256"])):
                raise ValueError("NBP source fingerprint required")
            if not isinstance(row["nbp_retrieved_at"], str) or not row["nbp_retrieved_at"]:
                raise ValueError("NBP retrieval timestamp required")
            cash_baseline += payment
            theoretical_pre_cost_value = units * price
            gross_units += payment / price
            cost_rate = (fee + slip) / D("10000")
            added_notional = payment / (D("1") + cost_rate)
            friction = payment - added_notional
            units += added_notional / price
            cumulative_friction += friction
            after = units * price
            timeline.append({
                "month": month,
                "source_date": day.isoformat(),
                "hypothetical_nav_reference_value_pln": format(after.quantize(D(".01")), "f"),
                "cash_baseline_pln": format(cash_baseline.quantize(D(".01")), "f"),
                "hypothetical_incurred_cost_pln": format(friction.quantize(D(".0001")), "f"),
                "input_source_row_sha256": _digest(row),
            })
            last_month, last_day, last_price = month, day, price
        net = units * last_price
        gross = gross_units * last_price
        out = {
            "schema": SCHEMA,
            "status": "CONDITIONAL_HISTORICAL_NAV_REFERENCE_NOT_INVESTABLE_BACKTEST",
            "periods": len(rows),
            "first_month": rows[0]["month"], "last_month": rows[-1]["month"],
            "monthly_contribution_pln": str(payment),
            "assumed_fee_bps": str(fee), "assumed_slippage_bps": str(slip),
            "contributions_pln": format(cash_baseline.quantize(D(".01")), "f"),
            "cash_reference_final_pln": format(cash_baseline.quantize(D(".01")), "f"),
            "nav_reference_gross_final_pln": format(gross.quantize(D(".01")), "f"),
            "nav_reference_net_final_pln": format(net.quantize(D(".01")), "f"),
            "hypothetical_cumulative_frictions_pln": format(cumulative_friction.quantize(D(".01")), "f"),
            "conditional_difference_vs_cash_pln": format((net - cash_baseline).quantize(D(".01")), "f"),
            "source_evidence_sha256": artifact["evidence_sha256"],
            "nav_file_sha256": artifact.get("nav_candidate_file_sha256"),
            "nav_quote_kind": "NON_EXECUTABLE_ACCUMULATING_FUND_NAV_REFERENCE_PLN",
            "cash_assumed_interest": "0",
            "month_end_fractional_units_not_real_fills": True,
            "historical_point_in_time_certified": False,
            "source_rights_independently_certified": False,
            "m1_qualified_model_backtest": False,
            "prospective_out_of_sample_performance": False,
            "statistical_edge_or_alpha_proven": False,
            "orders_sent": 0, "paper_fills": 0, "database_writes": 0,
            "financial_operations": 0,
            "timeline": timeline,
        }
        out["research_receipt_sha256"] = _digest(out)
        return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--nav-receipt", type=Path, required=True)
    p.add_argument("--fee-bps", default="20")
    p.add_argument("--slippage-bps", default="10")
    args = p.parse_args()
    if (args.nav_receipt.is_symlink() or not args.nav_receipt.is_file()
            or args.nav_receipt.stat().st_size > 3_000_000):
        raise ValueError("bounded private regular source file required")
    report = evaluate_nav_reference(json.loads(
        args.nav_receipt.read_text(encoding="utf-8")),
        fee_bps=args.fee_bps, slippage_bps=args.slippage_bps)
    # Don't publish daily/monthly original price levels or proprietary rows.
    summary = {k:v for k,v in report.items() if k != "timeline"}
    print("ISL_CONDITIONAL_M1_NAV_V20=" +
          json.dumps(summary, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
