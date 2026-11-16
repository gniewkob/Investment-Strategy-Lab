"""Offline educational monthly-contribution scenario engine (synthetic or unverified inputs).

Explicit PLN price observations only. No inferred historical prices, network,
portfolio storage, live execution, or strategy admission. Cash is the baseline.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

SCHEMA = "ISL_PAPER_SCENARIO_ENGINE_V01"


class ScenarioBlocked(ValueError):
    """Input or simulation invariant failed closed."""


def _money(value: object, *, allow_zero: bool = True) -> Decimal:
    if type(value) not in (str, int, Decimal):
        raise ScenarioBlocked("DECIMAL_INPUT_REQUIRED")
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ScenarioBlocked("DECIMAL_INPUT_INVALID") from exc
    if not number.is_finite() or number < 0 or (not allow_zero and number == 0):
        raise ScenarioBlocked("NONNEGATIVE_FINITE_VALUE_REQUIRED")
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
