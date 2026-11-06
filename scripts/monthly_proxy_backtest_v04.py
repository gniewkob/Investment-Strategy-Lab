"""Pure monthly M1/M2/M3 benchmark-proxy backtest; educational, no execution.

IMPORTANT: This engine assumes fractional units of NON-EXECUTABLE PLN total
return benchmarks to test portfolio arithmetic, not paper-trade fills.
Historical reconstructions are NOT certified point-in-time availability:
timestamps and hashes supplied in manifests are not independent proof.
It makes no network calls, opens no accounts, and never connects to a DB.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ASSETS = ("GLOBAL_EQUITY_TR_PLN", "PL_BONDS_TR_PLN", "GOLD_TR_PLN")
MODELS = ("M1_GLOBAL_EQ", "M2_DIVERSIFIED", "M3_TACTICAL")
D = Decimal
ONE = D("1")
ZERO = D("0")
BPS = D("10000")
MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_MONTHS = 360
MOMENTUM_MONTHS = 3
MIN_MONTHS = 10  # synthetic/offline algorithm tests
MIN_HISTORICAL_MONTHS = 36  # minimum research horizon, not evidence quality
POLICY = {
    "M1_GLOBAL_EQ": {"GLOBAL_EQUITY_TR_PLN": D("1")},
    "M2_DIVERSIFIED": {
        "GLOBAL_EQUITY_TR_PLN": D(".6"),
        "PL_BONDS_TR_PLN": D(".3"),
        "GOLD_TR_PLN": D(".1"),
    },
    "M3_RISK_ON": {
        "GLOBAL_EQUITY_TR_PLN": D(".6"),
        "PL_BONDS_TR_PLN": D(".3"),
        "GOLD_TR_PLN": D(".1"),
    },
    "M3_RISK_OFF": {
        "GLOBAL_EQUITY_TR_PLN": D(".3"),
        "PL_BONDS_TR_PLN": D(".3"),
        "GOLD_TR_PLN": D(".1"),
    },
}
SOURCES_REQUIRED = frozenset(ASSETS)


class BacktestValidationError(ValueError):
    pass


def _decimal(value: object, field: str, *, zero_ok: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise BacktestValidationError(field + " must be a decimal string or integer")
    if isinstance(value, str) and (value.strip() != value or not value):
        raise BacktestValidationError(field + " has invalid whitespace or is empty")
    try:
        val = D(str(value))
    except (ValueError, InvalidOperation) as exc:
        raise BacktestValidationError(field + " is not decimal") from exc
    if not val.is_finite() or val < 0 or (val == 0 and not zero_ok):
        raise BacktestValidationError(field + " must be finite and positive")
    return val


def _utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise BacktestValidationError("ISO timestamp required")
    try:
        val = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BacktestValidationError("invalid ISO timestamp") from exc
    if val.tzinfo is None or val.utcoffset() != timedelta(0):
        raise BacktestValidationError("explicit UTC timestamp required")
    return val.astimezone(timezone.utc)


def _month(value: object) -> tuple[int, int]:
    if not isinstance(value, str) or not MONTH_RE.fullmatch(value):
        raise BacktestValidationError("YYYY-MM month required")
    year, m = (int(x) for x in value.split("-"))
    if not 1 <= m <= 12 or not 2000 <= year <= 2100:
        raise BacktestValidationError("invalid or unsupported month")
    return year, m


def _next_month(ym: tuple[int, int]) -> tuple[int, int]:
    year, month = ym
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _https_url(value: object) -> None:
    if not isinstance(value, str):
        raise BacktestValidationError("HTTPS provenance URL required")
    try:
        u = urlsplit(value)
    except ValueError as exc:
        raise BacktestValidationError("bad source URL") from exc
    if (u.scheme != "https" or not u.hostname or u.username is not None
            or u.password is not None or u.fragment):
        raise BacktestValidationError("source must have public HTTPS URL")


def _str(value: Decimal, places: str = "0.01") -> str:
    return format(value.quantize(D(places)), "f")


def _fingerprint(value: object) -> str:
    try:
        data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise BacktestValidationError("non-canonical input payload") from exc
    return sha256(data.encode("utf-8")).hexdigest()


def _required_missing(payload: dict) -> list[str]:
    series = payload.get("series")
    if not isinstance(series, dict):
        return list(ASSETS)
    return [code for code in ASSETS if
            not isinstance(series.get(code), dict)
            or not isinstance(series[code].get("rows"), list)
            or not series[code]["rows"]]


def validate(payload: object) -> tuple[dict, list[dict]] | tuple[dict, None]:
    if not isinstance(payload, dict):
        raise BacktestValidationError("JSON object required")
    if payload.get("mode") != "EDUCATIONAL_RESEARCH_ONLY":
        raise BacktestValidationError("research-only mode required")
    vintage = payload.get("source_vintage")
    if vintage not in ("SYNTHETIC_OFFLINE_FIXTURE",
                       "HISTORICAL_RESEARCH_RECONSTRUCTION"):
        raise BacktestValidationError("unsupported source vintage")
    if payload.get("historical_pit_certified", False) is not False:
        raise BacktestValidationError("manifest cannot self-certify historical PIT")
    contribution = _decimal(payload.get("monthly_contribution_pln"),
                            "monthly contribution")
    fee = _decimal(payload.get("fee_bps"), "fee", zero_ok=True)
    slippage = _decimal(payload.get("slippage_bps"), "slippage", zero_ok=True)
    if contribution > D("100000") or fee > 200 or slippage > 200:
        raise BacktestValidationError("unbounded contribution or cost")
    periods = payload.get("periods")
    if not isinstance(periods, list) or not 1 <= len(periods) <= MAX_MONTHS:
        raise BacktestValidationError("bounded monthly decision periods required")
    train_periods = payload.get("training_periods")
    if not isinstance(train_periods, int) or isinstance(train_periods, bool):
        raise BacktestValidationError("integer training_periods required")
    if train_periods < 4 or len(periods) - train_periods < 4:
        raise BacktestValidationError("training and test windows need >=4 months")

    settings = dict(monthly_contribution=contribution, fee=fee, slippage=slippage,
                    vintage=vintage, training_periods=train_periods)
    missing = _required_missing(payload)
    if missing:
        # Not even a hypothetical performance result is created.
        return settings, None
    series = payload["series"]
    if set(series) != SOURCES_REQUIRED:
        raise BacktestValidationError("unexpected asset series")
    n = len(periods)
    if n < MIN_MONTHS:
        raise BacktestValidationError("at least 10 monthly periods required")
    for asset in ASSETS:
        s = series[asset]
        if not isinstance(s, dict) or set(s) != {
            "quote_currency", "return_basis", "instrument_kind",
            "source_url", "source_sha256", "rows",
        }:
            raise BacktestValidationError("unexpected source metadata")
        if s["quote_currency"] != "PLN" or s["return_basis"] != "TOTAL_RETURN":
            raise BacktestValidationError("validated PLN total-return proxy required")
        if s["instrument_kind"] != "NON_EXECUTABLE_BENCHMARK":
            raise BacktestValidationError("indexes cannot be executable prices")
        _https_url(s["source_url"])
        if (not isinstance(s["source_sha256"], str)
                or not HEX64_RE.fullmatch(s["source_sha256"])):
            raise BacktestValidationError("source raw SHA-256 required")
        if not isinstance(s["rows"], list) or len(s["rows"]) != n:
            raise BacktestValidationError("complete aligned series required")

    parsed = []
    last_ym = None
    last_decision = None
    for i, period in enumerate(periods):
        if not isinstance(period, dict) or set(period) != {"month", "decision_at"}:
            raise BacktestValidationError("month and decision_at only")
        ym = _month(period["month"])
        if last_ym is not None and ym != _next_month(last_ym):
            raise BacktestValidationError("duplicate or missing calendar month")
        decision = _utc(period["decision_at"])
        if (vintage == "HISTORICAL_RESEARCH_RECONSTRUCTION"
                and decision > datetime.now(timezone.utc)):
            raise BacktestValidationError("future date cannot be historical observation")
        if last_decision is not None and decision <= last_decision:
            raise BacktestValidationError("decision timestamps out of order")
        # These are observed month-end benchmark values; the decision is
        # AFTER their availability, never a fill at the historical close.
        if (decision.date().year, decision.date().month) != _next_month(ym):
            raise BacktestValidationError("decision must be in the immediately following month")
        levels = {}
        references = {}
        for asset in ASSETS:
            item = series[asset]["rows"][i]
            if not isinstance(item, dict) or set(item) != {
                "month", "observed_for", "first_usable_at", "level_pln",
            }:
                raise BacktestValidationError("unexpected benchmark observation")
            if item["month"] != period["month"]:
                raise BacktestValidationError("unaligned monthly benchmark input")
            try:
                observed = date.fromisoformat(item["observed_for"])
            except (ValueError, TypeError) as exc:
                raise BacktestValidationError("invalid observed_for") from exc
            if (observed.year, observed.month) != ym or observed.day < 20:
                raise BacktestValidationError("benchmark must be a late-month observation")
            available = _utc(item["first_usable_at"])
            if available.date() <= observed or available > decision:
                raise BacktestValidationError("look-ahead or unavailable monthly benchmark")
            level = _decimal(item["level_pln"], "benchmark level")
            levels[asset] = level
            references[asset] = {
                "observed_for": observed.isoformat(),
                "first_usable_at": available.isoformat(),
                "source_sha256": series[asset]["source_sha256"],
            }
        parsed.append({"month":period["month"], "decision_at":decision,
                       "levels":levels, "references":references})
        last_ym, last_decision = ym, decision
    return settings, parsed


def _positions_value(cash: Decimal, units: dict, levels: dict) -> Decimal:
    return cash + sum((units[a] * levels[a] for a in ASSETS), ZERO)


def _targets(model: str, history: list[dict], i: int) -> tuple[dict, str]:
    if model == "M1_GLOBAL_EQ":
        return POLICY["M1_GLOBAL_EQ"], "EQUITY_ONLY_PREDECLARED"
    if model == "M2_DIVERSIFIED":
        return POLICY["M2_DIVERSIFIED"], "DIVERSIFIED_PREDECLARED"
    if i < MOMENTUM_MONTHS:
        return {}, "MOMENTUM_WARMUP_HOLD_CASH"
    # All four observations are from completed monthly periods already
    # available at the current decision. The current decision earns only
    # the NEXT period's index return, never an earlier return.
    current = history[i]["levels"]["GLOBAL_EQUITY_TR_PLN"]
    historical = history[i - MOMENTUM_MONTHS]["levels"]["GLOBAL_EQUITY_TR_PLN"]
    return (POLICY["M3_RISK_ON"], "MOMENTUM_RISK_ON") if current > historical \
        else (POLICY["M3_RISK_OFF"], "MOMENTUM_RISK_OFF")


def _simulate(model: str, settings: dict, rows: list[dict]) -> dict:
    cash = ZERO
    holdings = {a: ZERO for a in ASSETS}
    total_contributed = total_fees = total_slippage = turnover = ZERO
    trade_count = 0
    twr = ONE
    twr_peak = ONE
    max_dd = ZERO
    train_twr = test_twr = ONE
    previous_after = None
    timeline = []
    for i, row in enumerate(rows):
        with localcontext() as ctx:
            ctx.prec = 40
            levels = row["levels"]
            before = _positions_value(cash, holdings, levels)
            growth = ONE if previous_after is None else before / previous_after
            cash += settings["monthly_contribution"]
            total_contributed += settings["monthly_contribution"]
            nominal_available = before + settings["monthly_contribution"]
            target, reason = _targets(model, rows, i)
            if sum(target.values(), ZERO) > ONE:
                raise AssertionError("target leverage")
            period_fees = period_slippage = ZERO
            cost_rate = (settings["fee"] + settings["slippage"]) / BPS
            # Sell only holdings exceeding targets; never sell unowned units.
            for asset in ASSETS:
                held = holdings[asset] * levels[asset]
                desired = nominal_available * target.get(asset, ZERO)
                if held > desired:
                    amount = held - desired
                    holdings[asset] -= amount / levels[asset]
                    fee = amount * settings["fee"] / BPS
                    slip = amount * settings["slippage"] / BPS
                    cash += amount - fee - slip
                    period_fees += fee
                    period_slippage += slip
                    turnover += amount
                    trade_count += 1
            # Buy benchmark-proxy fractional units as an ACCOUNTING SCENARIO,
            # not as tradable orders, at validated month-end reference levels.
            for asset in ASSETS:
                held = holdings[asset] * levels[asset]
                desired = nominal_available * target.get(asset, ZERO)
                deficit = max(ZERO, desired - held)
                amount = min(deficit, cash / (ONE + cost_rate))
                if amount > ZERO:
                    holdings[asset] += amount / levels[asset]
                    fee = amount * settings["fee"] / BPS
                    slip = amount * settings["slippage"] / BPS
                    cash -= amount + fee + slip
                    period_fees += fee
                    period_slippage += slip
                    turnover += amount
                    trade_count += 1
            if cash < D("-0.00000000000000000001") or any(
                    n < ZERO for n in holdings.values()):
                raise AssertionError("cash constraint violated")
            cash = max(cash, ZERO)
            after = _positions_value(cash, holdings, levels)
            # A monthly contribution is external cash flow, not profit.
            # Time-weighted wealth includes both market repricing and
            # explicit hypothetical rebalance costs.
            cost_factor = after / nominal_available
            factor = growth * cost_factor
            twr *= factor
            if i < settings["training_periods"]:
                train_twr *= factor
                segment = "IN_SAMPLE"
            else:
                test_twr *= factor
                segment = "OUT_OF_SAMPLE"
            twr_peak = max(twr_peak, twr)
            max_dd = max(max_dd, ONE - twr / twr_peak)
            total_fees += period_fees
            total_slippage += period_slippage
            timeline.append({
                "month": row["month"],
                "decision_at": row["decision_at"].isoformat(),
                "segment": segment,
                "signal": reason,
                "virtual_contribution_pln": _str(settings["monthly_contribution"]),
                "portfolio_reference_value_pln": _str(after),
                "cash_pln": _str(cash),
                "assumed_fee_pln": _str(period_fees),
                "assumed_slippage_pln": _str(period_slippage),
                "hypothetical_weights": {a: _str(target.get(a, ZERO), "0.0001")
                                         for a in ASSETS},
            })
            previous_after = after
    return {
        "model_code": model,
        "contributed_pln": _str(total_contributed),
        "end_reference_value_pln": _str(previous_after),
        "net_reference_pnl_pln": _str(previous_after - total_contributed),
        "simple_contribution_roi_pct": _str(
            (previous_after / total_contributed - ONE) * 100, "0.0001"),
        "flow_adjusted_twr_pct": _str((twr - ONE) * 100, "0.0001"),
        "in_sample_twr_pct": _str((train_twr - ONE) * 100, "0.0001"),
        "out_of_sample_twr_pct": _str((test_twr - ONE) * 100, "0.0001"),
        "flow_adjusted_max_drawdown_pct": _str(max_dd * 100, "0.0001"),
        "assumed_fees_pln": _str(total_fees),
        "assumed_slippage_pln": _str(total_slippage),
        "hypothetical_rebalance_count": trade_count,
        "hypothetical_turnover_pln": _str(turnover),
        "cash_pln": _str(cash),
        "final_fractional_reference_units": {
            a: format(holdings[a], ".12f") for a in ASSETS
        },
        "timeline": timeline,
    }


def run_backtest(payload: object) -> dict:
    settings, rows = validate(payload)
    digest = _fingerprint(payload)
    missing = _required_missing(payload)
    if rows is None:
        return {
            "status": "NOT_RUN_INSUFFICIENT_DATA",
            "models": list(MODELS),
            "missing_required_series": missing,
            "input_sha256": digest,
            "source_vintage": settings["vintage"],
            "historical_pit_certified": False,
            "performance_proven": False,
            "real_orders": 0, "paper_events_created": 0,
            "database_connections": 0, "database_writes": 0,
            "results": [],
        }
    if (settings["vintage"] == "HISTORICAL_RESEARCH_RECONSTRUCTION"
            and len(rows) < MIN_HISTORICAL_MONTHS):
        return {
            "status": "NOT_RUN_INSUFFICIENT_HISTORY",
            "models": list(MODELS),
            "available_months": len(rows),
            "minimum_historical_months": MIN_HISTORICAL_MONTHS,
            "missing_required_series": [],
            "input_sha256": digest,
            "source_vintage": settings["vintage"],
            "historical_pit_certified": False,
            "investment_performance_proven": False,
            "real_orders": 0, "paper_events_created": 0,
            "database_connections": 0, "database_writes": 0,
            "results": [],
        }
    results = [_simulate(m, settings, rows) for m in MODELS]
    baseline = D(results[0]["end_reference_value_pln"])
    for r in results:
        r["difference_vs_M1_reference_pln"] = _str(
            D(r["end_reference_value_pln"]) - baseline)
    return {
        "status": ("SYNTHETIC_TEST_ONLY" if
                   settings["vintage"] == "SYNTHETIC_OFFLINE_FIXTURE" else
                   "CONDITIONAL_HISTORICAL_RECONSTRUCTION"),
        "input_sha256": digest,
        "source_vintage": settings["vintage"],
        "first_observed_month": rows[0]["month"],
        "last_observed_month": rows[-1]["month"],
        "monthly_contribution_pln": str(settings["monthly_contribution"]),
        "training_periods": settings["training_periods"],
        "test_periods": len(rows) - settings["training_periods"],
        "fee_bps_assumption": str(settings["fee"]),
        "slippage_bps_assumption": str(settings["slippage"]),
        "accounting_basis": "NON_EXECUTABLE_FRACTIONAL_TOTAL_RETURN_INDEX_PROXY",
        "monthly_reference_levels_are_not_executable_quotes": True,
        "historical_pit_certified": False,
        "investment_performance_proven": False,
        "parameters_optimized": False,
        "fx_model_needed": False,
        "cash_interest_assumed": "0",
        "costs_are_scenarios_not_actual_broker_fees": True,
        "real_orders": 0, "paper_events_created": 0,
        "database_connections": 0, "database_writes": 0,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    result = run_backtest(json.loads(args.input.read_text(encoding="utf-8")))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
