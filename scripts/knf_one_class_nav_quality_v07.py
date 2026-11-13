"""Pure offline descriptive quality/variability of one KNF PLN primary-unit NAV.

Not a holding-period investor return, forward risk, annualized volatility,
VaR, fund recommendation, backtest, order or account operation.
Input must pass the existing original-source same-fund/currency/KID safeguards.
"""
from __future__ import annotations

from datetime import date,datetime,timezone,timedelta
from decimal import Decimal,localcontext
from hashlib import sha256
import json

from scripts.knf_original_unit_history_research_v06 import (
    evaluate_sample, _number, Blocked,
)


def describe_unit_nav(preview_raw: bytes, kid_list_raw: bytes,
                      history_raw: bytes, kid_detail_raw: bytes | None, *,
                      observed_at: datetime) -> dict:
    """Only bounded, previously validated one-unit original research bytes."""
    receipt=evaluate_sample(preview_raw,kid_list_raw,history_raw,kid_detail_raw,
                            at=observed_at)
    try:
        payload=json.loads(history_raw)
        rows=payload["content"]
        sample=sorted((date.fromisoformat(row["date"]),_number(row["valuation"]))
                      for row in rows)
    except (TypeError,KeyError,ValueError) as exc:
        raise Blocked("NAV_RESEARCH_SOURCE_SHAPE_INVALID") from exc
    days=[day for day,_ in sample]
    levels=[v for _,v in sample]
    if (len(days)!=receipt["daily_same_class_observations"]
            or days[0].isoformat()!=receipt["first_observation_day"]
            or days[-1].isoformat()!=receipt["last_observation_day"]
            or len(set(days))!=len(days)):
        raise Blocked("NAV_QUALITY_NOT_SAME_VALIDATED_HISTORY")
    if any(v<=0 or not v.is_finite() for v in levels):
        raise Blocked("NAV_QUALITY_INVALID_LEVEL")
    # This counts Monday-Friday calendar dates, NOT actual exchange sessions:
    # a legal holiday may be included, so the gap count is indicative only.
    weekdays=0
    cursor=days[0]
    while cursor<=days[-1]:
        if cursor.weekday()<5:
            weekdays+=1
        cursor+=timedelta(days=1)
    with localcontext() as ctx:
        ctx.prec=38
        changes=[((b/a)-Decimal(1))*100
                 for a,b in zip(levels,levels[1:])]
        avg=sum(changes,Decimal(0))/len(changes)
        variance=sum(((x-avg)**2 for x in changes),Decimal(0))/len(changes)
        stdev=variance.sqrt()
    def fixed(x):return format(x.quantize(Decimal("0.0001")),"f")
    out={
        "schema":"ISL_UKNF_ONE_CLASS_DESCRIPTIVE_NAV_QUALITY_V07",
        "status":"PRESENT_SNAPSHOT_VALIDATED_SAME_CLASS_NAV_REFERENCE_ONLY",
        "source":"UKNF_WYBIERAM_FUNDUSZE_API",
        "source_attribution":"https://wybieramfundusze-api.knf.gov.pl",
        "observed_by_runner_at_utc":observed_at.astimezone(timezone.utc).isoformat(),
        "source_history_sha256":receipt["source_documents"]["history_sha256"],
        "observed_first_day":days[0].isoformat(),
        "observed_last_day":days[-1].isoformat(),
        "same_unit_primary_pln":True,
        "distinct_valuation_days":len(days),
        "observed_adjacent_nav_level_changes":len(changes),
        "monday_friday_calendar_days_in_span_not_trading_sessions":weekdays,
        "unobserved_weekday_calendar_dates_not_verified_market_holidays":weekdays-len(days),
        "smallest_adjacent_observed_nav_level_change_pct":fixed(min(changes)),
        "largest_adjacent_observed_nav_level_change_pct":fixed(max(changes)),
        "mean_adjacent_observed_nav_level_change_pct":fixed(avg),
        "population_stddev_adjacent_observed_nav_level_change_pct_not_annualized":fixed(stdev),
        "first_to_last_nav_level_change_pct_not_total_return":receipt[
            "observed_nav_level_change_pct_not_total_return"],
        "kid_exact_same_class_match":receipt["kid_exact_fund_unit_currency_match"],
        "kid_risk_value_only_if_exact_matching":receipt[
            "kid_risk_level_descriptive_not_recommendation"],
        "kid_costs_only_if_exact_matching":receipt[
            "kid_stated_costs_rates_not_actual_fees"],
        "nav_distribution_adjusted_return":False,
        "historical_first_publication_proven":False,
        "annualized_volatility_estimate":False,
        "value_at_risk_claimed":False,
        "risk_forecast_or_fund_ranking":False,
        "asset_return_series_admitted":[],
        "model_m1_m2_m3":"INSUFFICIENT_DATA_HOLD_CASH",
        "database_writes":0,"orders":0,"financial_operations":0,
    }
    out["receipt_sha256"]=sha256(json.dumps(out,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return out
