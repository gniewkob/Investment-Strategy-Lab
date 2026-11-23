"""Three hypothetical PLN portfolios: deterministic, offline, non-executable paper research.

Does not connect to trading, sources, databases, or portfolio state. The monthly
close is a fictional mark and a hypothetical unit-price for fractional purchases,
not a transaction that could have been executed at a known point in time.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_UP
from hashlib import sha256
import json
from pathlib import Path

SCHEMA = "ISL_MULTI_ASSET_PAPER_RESEARCH_V02"
ASSETS = ("ASSET_A", "ASSET_B", "ASSET_C")
MODES = ("SYNTHETIC", "UNVERIFIED_EXTERNAL")
TOP_FIELDS = {"source_class", "currency", "simulation_mode", "monthly_contribution_pln",
              "observations", "strategies"}
STRATEGY_FIELDS = {"id", "weights_bps", "fee_rate", "fee_fixed_pln_per_order"}
OBSERVATION_FIELDS = {"month", "available_month", "levels_pln"}
DECIMAL_LIMIT = Decimal("1e12")


class MultiAssetBlocked(ValueError):
    """Input validation blocked comparison before any output is written."""


def number(value, *, positive=False):
    if type(value) not in (str, int, Decimal) or (isinstance(value, str) and
       (len(value) > 60 or value.strip() != value)):
        raise MultiAssetBlocked("INVALID_FINITE_DECIMAL")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise MultiAssetBlocked("INVALID_FINITE_DECIMAL") from exc
    if (not result.is_finite() or result < 0 or (positive and result <= 0)
            or result > DECIMAL_LIMIT or (result and result < Decimal("1e-12"))
            or len(result.as_tuple().digits) > 32):
        raise MultiAssetBlocked("INVALID_FINITE_DECIMAL")
    return result


def month(value):
    if not isinstance(value, str) or len(value) != 7 or value[4] != "-":
        raise MultiAssetBlocked("INVALID_MONTH")
    try:
        actual = date.fromisoformat(value + "-01")
    except ValueError as exc:
        raise MultiAssetBlocked("INVALID_MONTH") from exc
    if actual.strftime("%Y-%m") != value:
        raise MultiAssetBlocked("INVALID_MONTH")
    return value


def next_month(value):
    y, m = (int(v) for v in value.split("-"))
    return f"{y + (m == 12):04d}-{(m % 12) + 1:02d}"


def money(value):
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


def validated_manifest(payload):
    if type(payload) is not dict or set(payload) != TOP_FIELDS:
        raise MultiAssetBlocked("MANIFEST_SCHEMA_INVALID")
    if (payload["source_class"] not in MODES or payload["currency"] != "PLN"
            or payload["simulation_mode"] != "NON_EXECUTABLE_MONTH_END_FRACTIONAL_UNITS"):
        raise MultiAssetBlocked("UNQUALIFIED_INPUT_SEMANTICS")
    contribution = number(payload["monthly_contribution_pln"], positive=True)
    if contribution > Decimal("100000"):
        raise MultiAssetBlocked("CONTRIBUTION_TOO_LARGE")
    observations = payload["observations"]
    if type(observations) is not list or not 36 <= len(observations) <= 60:
        raise MultiAssetBlocked("MONTH_COUNT_OUT_OF_RESEARCH_HORIZON")
    months, levels = [], []
    for row in observations:
        if type(row) is not dict or set(row) != OBSERVATION_FIELDS:
            raise MultiAssetBlocked("OBSERVATION_SCHEMA_INVALID")
        m, available = month(row["month"]), month(row["available_month"])
        if available > m:
            raise MultiAssetBlocked("FUTURE_OBSERVATION_LOOKAHEAD")
        if type(row["levels_pln"]) is not dict or set(row["levels_pln"]) != set(ASSETS):
            raise MultiAssetBlocked("ASSET_SET_INCOMPLETE")
        months.append(m)
        levels.append({a: number(row["levels_pln"][a], positive=True) for a in ASSETS})
    if (months != sorted(set(months)) or
            any(n != next_month(m) for m, n in zip(months, months[1:]))):
        raise MultiAssetBlocked("MISSING_OR_DUPLICATE_MONTH")
    strategies = payload["strategies"]
    if type(strategies) is not list or len(strategies) != 3:
        raise MultiAssetBlocked("EXACTLY_THREE_RESEARCH_STRATEGIES_REQUIRED")
    configured = []
    for idx, row in enumerate(strategies):
        if type(row) is not dict or set(row) != STRATEGY_FIELDS or row["id"] != f"SIM_M{idx+1}":
            raise MultiAssetBlocked("RESEARCH_STRATEGY_SCHEMA_INVALID")
        weights = row["weights_bps"]
        if type(weights) is not dict or set(weights) != set(ASSETS):
            raise MultiAssetBlocked("ASSET_WEIGHTS_INVALID")
        if any(type(w) is not int or w < 0 or w > 10000 for w in weights.values()) or sum(weights.values()) != 10000:
            raise MultiAssetBlocked("WEIGHTS_MUST_SUM_TO_10000_BPS")
        fee_rate = number(row["fee_rate"])
        fixed = number(row["fee_fixed_pln_per_order"])
        if fee_rate >= 1 or fixed >= contribution:
            raise MultiAssetBlocked("FEE_INVALID")
        configured.append((row["id"], weights, fee_rate, fixed))
    return contribution, months, levels, configured


def _portfolio(id_, weights, fee_rate, fixed_fee, contribution, months, levels):
    positions = {a: Decimal(0) for a in ASSETS}
    fees_total = Decimal(0)
    peak = Decimal(1)
    tw_index = Decimal(1)
    worst_dd = Decimal(0)
    monthly_path = []
    previous = None
    previous_value = Decimal(0)
    for i, (m, prices) in enumerate(zip(months, levels)):
        # A time-weighted pre-contribution mark separates market changes from new deposits.
        before_contribution = sum((positions[a] * prices[a] for a in ASSETS), Decimal(0))
        if previous is not None:
            if previous_value <= 0:
                raise MultiAssetBlocked("INVALID_PRIOR_VALUATION")
            tw_index *= before_contribution / previous_value
            peak = max(peak, tw_index)
            worst_dd = max(worst_dd, Decimal(1) - tw_index / peak)
        fees_month = Decimal(0)
        for a in ASSETS:
            allocation = contribution * Decimal(weights[a]) / Decimal(10000)
            if not allocation:
                continue
            charge = fixed_fee + allocation * fee_rate
            if charge >= allocation:
                raise MultiAssetBlocked("FEE_EXCEEDS_ASSET_ALLOCATION")
            positions[a] += (allocation - charge) / prices[a]
            fees_month += charge
        fees_total += fees_month
        previous_value = sum((positions[a] * prices[a] for a in ASSETS), Decimal(0))
        monthly_path.append({
            "month": m,
            "contributed_pln": money(contribution * (i+1)),
            "marked_value_pln": money(previous_value),
            "fees_cumulative_pln": money(fees_total),
        })
        previous = m
    ending = previous_value
    return {"id": id_, "terminal_value_pln": money(ending),
            "difference_vs_cash_pln": money(ending-contribution*len(months)),
            "fees_paid_pln": money(fees_total),
            "flow_adjusted_max_drawdown_pct": money(worst_dd*100),
            "path": monthly_path}


def compare(payload):
    contribution, months, levels, configured = validated_manifest(payload)
    with localcontext() as ctx:
        ctx.prec = 48
        strategies = [_portfolio(id_, weights, fee, fixed, contribution, months, levels)
                      for id_, weights, fee, fixed in configured]
    amount = contribution*len(months)
    # Prices and strategies are exclusively fabricated or source-unverified.
    # Hash is a content fingerprint, not an as-of attestation or permission to use data.
    try:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise MultiAssetBlocked("NON_CANONICAL_INPUT") from exc
    return {"schema": SCHEMA,
            "status": "EDUCATIONAL_NON_EXECUTABLE_COMPARISON_ONLY",
            "source_class": payload["source_class"],
            "price_basis": "HYPOTHETICAL_MONTH_END_LEVEL_NOT_EXECUTABLE_CLOSE",
            "input_sha256": sha256(canonical.encode("utf-8")).hexdigest(),
            "months": len(months), "first_month": months[0], "last_month": months[-1],
            "nominal_contributions_pln": money(amount),
            "cash_baseline_pln": money(amount),
            "strategies": strategies,
            "flow_adjusted_drawdown_excludes_contribution_effect": True,
            "research_strategies_are_not_live_m1_m2_m3": True,
            "historical_point_in_time_certified": False,
            "executable_prices_certified": False,
            "qualified_total_return_series": [],
            "investment_recommendation": False,
            "paper_decision": "INSUFFICIENT_DATA_HOLD_CASH",
            "orders_sent": 0, "financial_operations": 0, "database_writes": 0}


def synthetic_manifest():
    # Contrasting fictional paths: never imported from market sources.
    growth_patterns = ((2,-3,4,1,-2,3), (1,1,0,-1,1,0), (5,-6,-3,8,-4,2))
    current = [Decimal("100")] * 3
    rows = []
    for i in range(60):
        for a in range(3):
            current[a] *= (Decimal(1) + Decimal(growth_patterns[a][i % 6]) / 100)
        m = f"{2021+i//12:04d}-{i%12+1:02d}"
        rows.append({"month": m, "available_month": m,
                     "levels_pln": {a: format(current[j].quantize(Decimal('0.000001')), 'f')
                                    for j, a in enumerate(ASSETS)}})
    return {"source_class": "SYNTHETIC", "currency": "PLN",
            "simulation_mode": "NON_EXECUTABLE_MONTH_END_FRACTIONAL_UNITS",
            "monthly_contribution_pln": "100", "observations": rows,
            "strategies": [
                {"id": "SIM_M1", "weights_bps": {"ASSET_A": 2000, "ASSET_B": 7000, "ASSET_C": 1000},
                 "fee_rate": "0.002", "fee_fixed_pln_per_order": "0.05"},
                {"id": "SIM_M2", "weights_bps": {"ASSET_A": 5000, "ASSET_B": 3000, "ASSET_C": 2000},
                 "fee_rate": "0.002", "fee_fixed_pln_per_order": "0.05"},
                {"id": "SIM_M3", "weights_bps": {"ASSET_A": 8000, "ASSET_B": 1000, "ASSET_C": 1000},
                 "fee_rate": "0.002", "fee_fixed_pln_per_order": "0.05"},
            ]}


def markdown(report):
    lines = ["# ISL — porównanie trzech fikcyjnych portfeli", "",
             f"Okres: {report['first_month']}–{report['last_month']}, "
             f"{report['months']} miesięcy, {report['nominal_contributions_pln']} PLN wpłat na wariant.", "",
             "| Wariant | Wartość końcowa PLN | Różnica vs gotówka PLN | Opłaty PLN | Obsunięcie TWR % |",
             "| --- | ---: | ---: | ---: | ---: |",
             f"| Gotówka | {report['cash_baseline_pln']} | 0.00 | 0.00 | 0.00 |"]
    for row in report["strategies"]:
        lines.append(f"| {row['id']} | {row['terminal_value_pln']} | {row['difference_vs_cash_pln']} "
                     f"| {row['fees_paid_pln']} | {row['flow_adjusted_max_drawdown_pct']} |")
    lines += ["", "**INSUFFICIENT_DATA_HOLD_CASH.** Wszystkie poziomy cen to fikcja albo "
              "dane nieweryfikowane. Zamknięcie miesiąca nie jest wykonywalną ceną zakupu. "
              "SIM_M1–M3 nie są skonfigurowanymi modelami inwestycyjnymi M1–M3. "
              "Obsunięcie liczone na indeksie wartości przed nową wpłatą; "
              "nie obejmuje pełnej realizowalności, podatków, spreadów i ryzyka płynności. "
              "Zero realnych operacji, zleceń i zapisów do bazy.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--synthetic-demo", action="store_true")
    choice.add_argument("--input", type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.synthetic_demo:
            payload = synthetic_manifest()
        else:
            if args.input.is_symlink() or not args.input.is_file() or args.input.stat().st_size > 1_000_000:
                raise MultiAssetBlocked("INVALID_INPUT_FILE")
            payload = json.loads(args.input.read_text(encoding="utf-8"))
        report = compare(payload)
        if args.out_dir.exists() or args.out_dir.is_symlink():
            raise MultiAssetBlocked("OUTPUT_DIRECTORY_ALREADY_EXISTS")
        args.out_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
        (args.out_dir / "comparison.json").write_text(
            json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (args.out_dir / "report.md").write_text(markdown(report), encoding="utf-8")
    except (MultiAssetBlocked, OSError, UnicodeError, ValueError, ArithmeticError) as exc:
        parser.error(str(exc))
    print("PAPER_MULTI_ASSET_V02="+json.dumps({
        "status":"PASS_SYNTHETIC_OR_UNVERIFIED_ONLY",
        "months":report["months"], "input_sha256":report["input_sha256"],
        "financial_operations":0, "database_writes":0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())