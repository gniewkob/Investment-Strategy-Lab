"""Offline educational monthly-contribution scenario engine (synthetic or unverified inputs).

Explicit PLN price observations only. No inferred historical prices, network,
portfolio storage, live execution, or strategy admission. Cash is the baseline.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path

SCHEMA = "ISL_PAPER_SCENARIO_ENGINE_V01"
MANIFEST_FIELDS = frozenset({
    "mode", "source_class", "currency", "price_basis", "monthly_contribution_pln",
    "observations", "strategies",
})
DEMO_PATTERN = (3, -2, 1, 4, -1, -3, 2, 0, -4, 5, 1, -1)


class ScenarioBlocked(ValueError):
    """Input or simulation invariant failed closed."""


def _money(value: object, *, allow_zero: bool = True) -> Decimal:
    if type(value) not in (str, int, Decimal):
        raise ScenarioBlocked("DECIMAL_INPUT_REQUIRED")
    if isinstance(value, str) and (len(value) > 80 or value.strip() != value):
        raise ScenarioBlocked("DECIMAL_INPUT_INVALID")
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ScenarioBlocked("DECIMAL_INPUT_INVALID") from exc
    if not number.is_finite() or number < 0 or (not allow_zero and number == 0):
        raise ScenarioBlocked("NONNEGATIVE_FINITE_VALUE_REQUIRED")
    # Bound both scale and precision before unit division; Decimal('1e-999999')
    # is finite but would otherwise overflow or exhaust arithmetic resources.
    if number and (not -18 <= number.adjusted() <= 18
                   or len(number.as_tuple().digits) > 32):
        raise ScenarioBlocked("DECIMAL_MAGNITUDE_OR_PRECISION_INVALID")
    return number


def _month(value: object) -> str:
    if not isinstance(value, str) or len(value) != 7 or value[4] != "-":
        raise ScenarioBlocked("MONTH_FORMAT_INVALID")
    try:
        d = date.fromisoformat(value + "-01")
    except ValueError as exc:
        raise ScenarioBlocked("MONTH_FORMAT_INVALID") from exc
    return d.strftime("%Y-%m")


def _next_month(m: str) -> str:
    y, n = map(int, m.split("-"))
    return f"{y + (n == 12):04d}-{(n % 12) + 1:02d}"


def run_scenario(*, observations: list[dict], monthly_contribution: str = "100",
                 fee_fixed_pln: str = "0", fee_rate: str = "0",
                 mode: str = "asset", source_class: str = "SYNTHETIC") -> dict:
    """Buy after each explicitly available monthly close; value at last close.

    Each input row has {month, price_pln, available_month}; availability must be
    no later than that trading month. Observations represent scenario execution
    prices, not invented trades or historical first-publication evidence.
    """
    if mode not in ("asset", "cash") or source_class not in ("SYNTHETIC", "UNVERIFIED_EXTERNAL"):
        raise ScenarioBlocked("SCENARIO_MODE_INVALID")
    if not isinstance(observations, list) or not 1 <= len(observations) <= 120:
        raise ScenarioBlocked("OBSERVATION_COUNT_INVALID")
    deposit = _money(monthly_contribution, allow_zero=False)
    fixed, rate = _money(fee_fixed_pln), _money(fee_rate)
    if deposit > 100000 or fixed > deposit or rate >= 1:
        raise ScenarioBlocked("CONTRIBUTION_OR_FEE_INVALID")
    parsed = []
    for row in observations:
        if not isinstance(row, dict) or set(row) != {"month", "price_pln", "available_month"}:
            raise ScenarioBlocked("OBSERVATION_SCHEMA_INVALID")
        month, available = _month(row["month"]), _month(row["available_month"])
        if available > month:
            raise ScenarioBlocked("LOOK_AHEAD_PRICE_UNAVAILABLE")
        parsed.append((month, _money(row["price_pln"], allow_zero=False)))
    months = [m for m, _ in parsed]
    if months != sorted(set(months)) or any(b != _next_month(a) for a, b in zip(months, months[1:])):
        raise ScenarioBlocked("MONTHLY_HISTORY_NONCONTIGUOUS")
    balance, units, total_fees = Decimal(0), Decimal(0), Decimal(0)
    rows = []
    for month, price in parsed:
        balance += deposit
        fee = Decimal(0)
        if mode == "asset":
            fee = fixed + deposit * rate
            if fee >= deposit:
                raise ScenarioBlocked("FEE_EXCEEDS_MONTHLY_CONTRIBUTION")
            units += (deposit - fee) / price
            balance -= deposit
            total_fees += fee
        value = balance + units * price
        rows.append({"month": month, "contributed_pln": str(deposit * (len(rows) + 1)),
                     "cash_pln": str(balance), "units": str(units),
                     "marked_value_pln": str(value), "fees_paid_pln": str(total_fees)})
    invested = deposit * len(parsed)
    ending = balance + units * parsed[-1][1]
    return {"schema": SCHEMA, "status": "EDUCATIONAL_SCENARIO_NOT_INVESTMENT_SIGNAL",
            "source_class": source_class, "scenario_mode": mode, "months": len(parsed),
            "contributions_pln": str(invested), "cash_baseline_pln": str(invested),
            "ending_value_pln": str(ending), "difference_vs_cash_pln": str(ending - invested),
            "total_fees_pln": str(total_fees), "monthly_path": rows,
            "historical_pit_certified": False, "model_admitted": False,
            "orders_sent": 0, "database_writes": 0, "financial_operations": 0}



def compare_scenarios(*, observations: list[dict], strategies: list[dict],
                      monthly_contribution: str = "100",
                      source_class: str = "SYNTHETIC") -> dict:
    """Compare explicitly configured strategies on identical monthly observations.

    Rank by terminal scenario value only; no annualized-return or investment
    recommendation claims. Include cash as a mandatory zero-cost baseline.
    """
    if not isinstance(strategies, list) or not 1 <= len(strategies) <= 12:
        raise ScenarioBlocked("STRATEGY_COUNT_INVALID")
    names = set()
    configured = []
    for candidate in strategies:
        if (not isinstance(candidate, dict)
                or set(candidate) != {"name", "fee_fixed_pln", "fee_rate"}):
            raise ScenarioBlocked("STRATEGY_SCHEMA_INVALID")
        name = candidate["name"]
        if (not isinstance(name, str) or not 1 <= len(name) <= 40
                or not all(c.isalnum() or c in " _-." for c in name)
                or name.lower() == "cash" or name.lower() in names):
            raise ScenarioBlocked("STRATEGY_NAME_INVALID_OR_DUPLICATE")
        names.add(name.lower())
        configured.append((name, candidate))

    baseline = run_scenario(observations=observations,
                            monthly_contribution=monthly_contribution,
                            mode="cash", source_class=source_class)
    result = [{"name": "cash", "ending_value_pln": baseline["ending_value_pln"],
               "difference_vs_cash_pln": "0", "total_fees_pln": "0",
               "scenario_mode": "cash"}]
    for name, strategy in configured:
        scenario = run_scenario(
            observations=observations, monthly_contribution=monthly_contribution,
            fee_fixed_pln=strategy["fee_fixed_pln"], fee_rate=strategy["fee_rate"],
            source_class=source_class)
        result.append({"name": name, "ending_value_pln": scenario["ending_value_pln"],
                       "difference_vs_cash_pln": scenario["difference_vs_cash_pln"],
                       "total_fees_pln": scenario["total_fees_pln"],
                       "scenario_mode": "asset"})
    # A single terminal valuation ranking is intentionally not a risk-adjusted
    # performance claim: no future return or investment signal is inferred.
    ranked = sorted(result, key=lambda item: (-Decimal(item["ending_value_pln"]),
                                               item["name"]))
    return {"schema": "ISL_PAPER_SCENARIO_COMPARISON_V01",
            "status": "DESCRIPTIVE_SYNTHETIC_OR_UNVERIFIED_SCENARIOS_ONLY",
            "source_class": source_class, "months": baseline["months"],
            "contributions_pln": baseline["contributions_pln"],
            "comparison": ranked, "ranking_is_investment_recommendation": False,
            "historical_pit_certified": False, "model_admitted": False,
            "orders_sent": 0, "database_writes": 0, "financial_operations": 0}


def synthetic_demo_manifest() -> dict:
    """Five years of fully invented observations for offline acceptance only."""
    price = Decimal("100")
    rows = []
    for index in range(60):
        price = (price * (Decimal("1") + Decimal(DEMO_PATTERN[index % 12]) / 100))
        month = f"{2021 + index // 12:04d}-{index % 12 + 1:02d}"
        rows.append({"month": month, "available_month": month,
                     "price_pln": str(price.quantize(Decimal("0.0001")))})
    return {"mode": "EDUCATIONAL_PAPER_ONLY", "source_class": "SYNTHETIC",
            "currency": "PLN", "price_basis": "EXPLICIT_MONTHLY_PLN_SCENARIO_PRICE",
            "monthly_contribution_pln": "100", "observations": rows,
            "strategies": [
                {"name": "zero cost", "fee_fixed_pln": "0", "fee_rate": "0"},
                {"name": "cost 0.2pct", "fee_fixed_pln": "0", "fee_rate": "0.002"},
                {"name": "cost 0.7pct", "fee_fixed_pln": "0", "fee_rate": "0.007"},
                {"name": "cost 1.5pct", "fee_fixed_pln": "0", "fee_rate": "0.015"},
                {"name": "fixed 1pln plus 0.7pct", "fee_fixed_pln": "1", "fee_rate": "0.007"},
            ]}


def analyze_manifest(payload: object) -> dict:
    """Read-only deterministic comparison; provenance is never self-certified."""
    if not isinstance(payload, dict) or set(payload) != MANIFEST_FIELDS:
        raise ScenarioBlocked("MANIFEST_SCHEMA_INVALID")
    if (payload["mode"] != "EDUCATIONAL_PAPER_ONLY" or payload["currency"] != "PLN"
            or payload["price_basis"] != "EXPLICIT_MONTHLY_PLN_SCENARIO_PRICE"):
        raise ScenarioBlocked("MANIFEST_RESEARCH_ONLY_PLN_PRICE_BASIS_REQUIRED")
    # No VERIFIED status: source origin, first-release timestamps, corporate
    # actions and an executable quote are not established by this manifest.
    if payload["source_class"] not in ("SYNTHETIC", "UNVERIFIED_EXTERNAL"):
        raise ScenarioBlocked("MANIFEST_SOURCE_UNQUALIFIED")
    result = compare_scenarios(
        observations=payload["observations"], strategies=payload["strategies"],
        monthly_contribution=payload["monthly_contribution_pln"],
        source_class=payload["source_class"])
    try:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ScenarioBlocked("MANIFEST_NOT_CANONICAL_JSON") from exc
    result.update({"input_sha256": sha256(canonical.encode("utf-8")).hexdigest(),
                   "first_month": payload["observations"][0]["month"],
                   "last_month": payload["observations"][-1]["month"],
                   "currency": "PLN", "price_basis": payload["price_basis"],
                   "paper_decision": "HOLD_CASH",
                   "input_hash_proves_source_authenticity": False})
    return result


def render_markdown_report(result: dict) -> str:
    """A descriptive cost-sensitivity report, not a return forecast."""
    def pln(value: str) -> str:
        return format(Decimal(value).quantize(Decimal("0.01")), ".2f")

    lines = [
        "# Investment Strategy Lab — monthly paper scenario report",
        "",
        "**Decision: HOLD_CASH** — educational comparison only; not an investment signal.",
        "",
        f"- Input class: `{result['source_class']}` (unqualified for model admission)",
        f"- Period: {result['first_month']} to {result['last_month']} ({result['months']} monthly marks)",
        f"- Fictional contribution: {pln(result['contributions_pln'])} PLN per alternative scenario",
        f"- Input SHA-256: `{result['input_sha256']}` (integrity fingerprint, not authenticity or PIT proof)",
        "- Pricing: explicit PLN scenario levels; not independently verified total-return indices or executable quotes",
        "- Costs: named scenarios differ in fees on purchases of fractional units; cash has zero fees and zero interest",
        "",
        "| Scenario | Terminal value (PLN) | Difference vs cash (PLN) | Total fees (PLN) |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in result["comparison"]:
        lines.append(f"| {row['name']} | {pln(row['ending_value_pln'])} | "
                     f"{pln(row['difference_vs_cash_pln'])} | {pln(row['total_fees_pln'])} |")
    lines.extend(["", "Synthetic/unverified price levels cannot prove historical "
                  "point-in-time availability, execution feasibility, annualized "
                  "returns or future performance. The ranking is descriptive. "
                  "No orders, transfers, database writes or allocation changes.", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline paper scenario cost sensitivity")
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--input", type=Path, help="Strict JSON research-only input")
    choice.add_argument("--synthetic-demo", action="store_true", help="Generate 60 fictional months")
    parser.add_argument("--out-dir", type=Path, required=True,
                        help="Local directory for comparison.json and report.md")
    args = parser.parse_args(argv)
    try:
        if args.synthetic_demo:
            payload = synthetic_demo_manifest()
        else:
            data = args.input.read_bytes()
            if len(data) > 1_000_000:
                raise ScenarioBlocked("MANIFEST_TOO_LARGE")
            payload = json.loads(data)
        result = analyze_manifest(payload)
    except (ScenarioBlocked, OSError, UnicodeError, ValueError) as exc:
        parser.error(f"input rejected: {exc}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "comparison.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8")
    (args.out_dir / "report.md").write_text(render_markdown_report(result),
                                             encoding="utf-8")
    print(f"OFFLINE_PAPER_REPORT {args.out_dir / 'comparison.json'} "
          f"{args.out_dir / 'report.md'} HOLD_CASH")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
