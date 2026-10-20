"""Conservative retrospective EIA STEO source-vintage robustness diagnostics.

No network/files/database/broker side effects. Input consists only of validated
historical forecast pairs and already parsed official archived STEO editions.
A date-labelled later edition is NOT independent evidence that the bytes were
present unchanged on its historically listed release date.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from itertools import groupby

from scripts.steo_monthly_forecast_eval import HEADERS, _add_month, _ym
from src.isl_v2.eia_sources import SourceFormatError


def _dec(value: str) -> Decimal:
    if not isinstance(value, str):
        raise SourceFormatError("Expected documented decimal provenance")
    try:
        v = Decimal(value)
    except InvalidOperation as exc:
        raise SourceFormatError("Invalid source observation decimal") from exc
    if not v.is_finite() or v < 0 or v > Decimal("1000000"):
        raise SourceFormatError("Source observation outside research limit")
    return v


def _rounded(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _check(result: dict, editions: list[dict]) -> list[dict]:
    if (result.get("status") != "STEO_RECONSTRUCTED_HISTORICAL_FORECAST_ERROR_COMPARISON"
            or result.get("historical_source_as_published_bytes_certified") is not False
            or result.get("original_observation_point_in_time_certified") is not False
            or result.get("returns_or_trading_backtest") is not False):
        raise SourceFormatError("Unsupported retrospective research proof")
    if (not 2 <= len(editions) <= 34 or len({x["issue"] for x in editions}) != len(editions)
            or result["source_editions"] != len(editions)):
        raise SourceFormatError("Source edition coverage mismatch")
    if any(x.get("original_first_release_bytes_certified") is not False for x in editions):
        raise SourceFormatError("Independent original publication proof not available")
    rows = result["paired_records"]
    if not rows or result["paired_target_forecasts"] != len(rows):
        raise SourceFormatError("Missing paired target observations")
    allow_instruments = {inst for inst, _ in HEADERS.values()}
    keys = set()
    for row in rows:
        instrument = row["instrument_code"]
        horizon = row["horizon_calendar_months"]
        target = row["target_month"]
        issued = row["edition_release_day"]
        ref = row["reference_edition_release_day"]
        if (instrument not in allow_instruments or type(horizon) is not int or
                horizon not in (1,3,6) or len(target) != 7 or
                date.fromisoformat(target+"-01") <= date.fromisoformat(issued) or
                date.fromisoformat(ref) <= date.fromisoformat(issued)):
            raise SourceFormatError("Invalid chronological forecast and reference pairing")
        rowkey = (instrument, horizon, target)
        if rowkey in keys:
            raise SourceFormatError("Duplicate same-instrument/horizon target month")
        keys.add(rowkey)
        _dec(row["source_forecast_value"])
        _dec(row["later_edition_reference_value"])
        _dec(row["same_edition_previous_month_naive_value"])
        # Recheck persisted pair error values against the source math.
        source = _dec(row["source_forecast_value"])
        naive = _dec(row["same_edition_previous_month_naive_value"])
        actual = _dec(row["later_edition_reference_value"])
        if (abs(source - actual) != _dec(row["absolute_source_forecast_error"])
                or abs(naive - actual) != _dec(row["absolute_naive_error"])):
            raise SourceFormatError("Paired absolute forecast errors contradict saved source values")
    return rows


def _select_preceding_observed(rows: list[dict], as_of_day: str) -> list[dict]:
    """Use only outcomes reported STRICTLY BEFORE current candidate forecast."""
    return [r for r in rows
            if r["reference_edition_release_day"] < as_of_day
            and r["edition_release_day"] < as_of_day]


def walkforward_audit(result: dict, editions: list[dict], min_matured: int = 6) -> dict:
    """Predeclared educational EIA-vs-naive selection using matured older labels.

    No parameter tuning, selection across horizons, or claims of investable
    backtests. Evaluates selected source-rule on future-issued forecasts only.
    """
    if type(min_matured) is not int or not 3 <= min_matured <= 16:
        raise SourceFormatError("Walk-forward minimum evidence not supported")
    rows = _check(result, editions)
    grouped: dict[tuple[str,int],list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["instrument_code"],row["horizon_calendar_months"])].append(row)

    output=[]
    for (instrument,horizon), examples in sorted(grouped.items()):
        samples=sorted(examples,key=lambda x:x["edition_release_day"])
        decisions=[]
        for current in samples:
            past = _select_preceding_observed(samples, current["edition_release_day"])
            if len(past) < min_matured:
                continue
            gain_history=sum((_dec(p["absolute_naive_error"]) -
                              _dec(p["absolute_source_forecast_error"]) for p in past),
                             Decimal("0"))
            choice = "EIA_STEO" if gain_history > 0 else "NAIVE_LAST_MONTH"
            chosen = (_dec(current["absolute_source_forecast_error"])
                      if choice=="EIA_STEO" else _dec(current["absolute_naive_error"]))
            decisions.append({
                "forecast_edition": current["forecast_edition"],
                "forecast_issue_day": current["edition_release_day"],
                "target_month": current["target_month"],
                "reference_issue_day": current["reference_edition_release_day"],
                "matured_training_pairs_known_by_issue_day":len(past),
                "latest_matured_reference_day":max(x["reference_edition_release_day"] for x in past),
                "predeclared_rule_chosen":choice,
                "chosen_absolute_error_usd_bbl":_rounded(chosen),
                "eia_absolute_error_usd_bbl":_rounded(_dec(current["absolute_source_forecast_error"])),
                "naive_absolute_error_usd_bbl":_rounded(_dec(current["absolute_naive_error"])),
            })
        if decisions:
            count=len(decisions)
            avg=lambda key: _rounded(sum((_dec(p[key]) for p in decisions),Decimal("0"))/count)
            output.append({
                "instrument_code":instrument,
                "horizon_calendar_months":horizon,
                "matured_min_train_pairs":min_matured,
                "eligible_chronological_evaluations":count,
                "earliest_evaluation_issue":decisions[0]["forecast_edition"],
                "last_evaluation_issue":decisions[-1]["forecast_edition"],
                "dynamic_selected_mae_usd_bbl":avg("chosen_absolute_error_usd_bbl"),
                "always_eia_same_pairs_mae_usd_bbl":avg("eia_absolute_error_usd_bbl"),
                "always_naive_same_pairs_mae_usd_bbl":avg("naive_absolute_error_usd_bbl"),
                "selected_eia_count":sum(x["predeclared_rule_chosen"]=="EIA_STEO" for x in decisions),
                "selected_naive_count":sum(x["predeclared_rule_chosen"]=="NAIVE_LAST_MONTH" for x in decisions),
                "no_future_labels_used_in_rule_selection":all(
                    x["latest_matured_reference_day"] < x["forecast_issue_day"] for x in decisions),
                "decisions":decisions,
                "predictive_advantage_or_tradable_returns_established":False,
            })
    by_target: dict[tuple[str,str],set[int]] = defaultdict(set)
    for row in rows:
        by_target[(row["instrument_code"],row["target_month"])].add(row["horizon_calendar_months"])
    return {
        "status":"STEO_MATURED_LABEL_WALKFORWARD_RETROSPECTIVE_RESEARCH_ONLY",
        "historical_original_edition_bytes_as_published_certified":False,
        "independent_historical_PIT_certified":False,
        "no_future_reported_outcomes_as_model_inputs":True,
        "dedupe_unit":"ONE_FORECAST_PER_SOURCE_INSTRUMENT_HORIZON_TARGET_MONTH",
        "original_paired_records":len(rows),
        "unique_instrument_target_months_across_all_horizons":len(by_target),
        "reused_target_months_across_horizons":sum(len(v)>1 for v in by_target.values()),
        "horizons_never_pooled_for_rule_selection":True,
        "explicit_chronology_as_of_day":"STRICTLY_BEFORE_FORECAST_OFFICIAL_RELEASE_DAY",
        "groups":output,
        "training_or_evaluation_is_investable_portfolio_backtest":False,
        "research_decision":"DESCRIPTIVE_ONLY_NO_PORTFOLIO_ACTION",
        "database_connections":0,"database_writes":0,
        "real_orders":0,"virtual_rebalances":0,
    }


def reference_revision_audit(result: dict, editions: list[dict]) -> dict:
    """How much later archived source editions change a first eligible reference.

    Later revisions are observed across documents AS CURRENTLY HOSTED, without
    independently certifying the bytes available at their listed release days.
    """
    rows=_check(result, editions)
    ordered=sorted(editions, key=lambda r:r["official_release_day"])
    reverse={v[0]:k for k,v in HEADERS.items()}
    groups=defaultdict(list)
    for row in rows:
        target=row["target_month"]
        issued=row["edition_release_day"]
        after=_add_month(date.fromisoformat(target+"-01"),2)
        instrument=row["instrument_code"]
        code=reverse[instrument]
        candidates=[
            doc for doc in ordered
            if doc["official_release_day"] > issued
            and doc["official_release_day"][:7] >= after
            and doc["series"][code].get(target) is not None
        ]
        if not candidates or candidates[0]["issue"]!=row["reference_edition"]:
            raise SourceFormatError("Later archived reference chronology disagrees with forecast pair")
        later=candidates[-1]
        first_price=_dec(row["later_edition_reference_value"])
        if _dec(candidates[0]["series"][code][target]) != first_price:
            raise SourceFormatError("Earliest report reference differs from stored paired quote")
        latest_price=_dec(later["series"][code][target])
        forecast=_dec(row["source_forecast_value"])
        naive=_dec(row["same_edition_previous_month_naive_value"])
        groups[(instrument,row["horizon_calendar_months"])].append({
            "target":target,
            "first_reference_edition":row["reference_edition"],
            "latest_eligible_reference_edition":later["issue"],
            "has_independent_later_edition":len(candidates)>1,
            "first_vs_last_reference_value_changed":first_price!=latest_price,
            "absolute_reference_delta_usd_bbl":abs(latest_price-first_price),
            "eia_latest_reference_abs_error":abs(forecast-latest_price),
            "naive_latest_reference_abs_error":abs(naive-latest_price),
            "first_eia_absolute_error":_dec(row["absolute_source_forecast_error"]),
            "first_naive_absolute_error":_dec(row["absolute_naive_error"]),
        })
    report=[]
    for (instrument,horizon),group in sorted(groups.items()):
        eligible=[x for x in group if x["has_independent_later_edition"]]
        if not group:
            continue
        avg=lambda key: _rounded(sum((x[key] for x in group),Decimal("0"))/len(group))
        report.append({
            "instrument_code":instrument,
            "horizon_calendar_months":horizon,
            "paired_forecasts":len(group),
            "later_reference_recheck_possible":len(eligible),
            "later_reference_changed":sum(x["first_vs_last_reference_value_changed"] for x in eligible),
            "largest_first_to_latest_reference_change_usd_bbl":
                _rounded(max((x["absolute_reference_delta_usd_bbl"] for x in eligible),default=Decimal("0"))),
            "first_eligible_source_reference_eia_mae_usd_bbl":avg("first_eia_absolute_error"),
            "latest_eligible_source_reference_eia_mae_usd_bbl":avg("eia_latest_reference_abs_error"),
            "first_eligible_source_reference_naive_mae_usd_bbl":avg("first_naive_absolute_error"),
            "latest_eligible_source_reference_naive_mae_usd_bbl":avg("naive_latest_reference_abs_error"),
            "original_source_bytes_historical_PIT_certified":False,
        })
    return {
        "status":"STEO_LATER_REPORT_REFERENCE_REVISION_SENSITIVITY_RESEARCH",
        "source_editions":len(ordered),
        "pairs":len(rows),
        "latest_eligible_reference_is_definitive_final_tradable_price":False,
        "historical_original_edition_bytes_as_published_certified":False,
        "reference_revision_does_not_establish_investable_advantage":True,
        "groups":report,
        "database_connections":0,"database_writes":0,
        "real_orders":0,"virtual_rebalances":0,
    }
