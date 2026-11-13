"""Source-grain-safe cross-market educational research quality receipt.

Reconciles ONE already-validated MF market turnover evidence, ONE original
UKNF same-class NAV research receipt and ONE pre-existing NBP/Eurostat public
macro receipt. It does NOT assert synchronized original historical publication,
price correlation, actual investor total return, portfolio signal or buy/sell.
"""
from __future__ import annotations

from datetime import datetime,timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re

SCHEMA="ISL_PUBLIC_CROSS_MARKET_SOURCE_QUALITY_V07"
SHA=re.compile(r"^[0-9a-f]{64}$")


class MarketQualityBlocked(ValueError):
    pass


def _sha(v):
    if not isinstance(v,str) or not SHA.fullmatch(v):
        raise MarketQualityBlocked("SOURCE_FINGERPRINT_UNVERIFIED_SHAPE")
    return v


def _utc(v):
    if not isinstance(v,str):
        raise MarketQualityBlocked("OBSERVATION_CLOCK_INVALID")
    try:
        dt=datetime.fromisoformat(v.replace("Z","+00:00"))
    except ValueError as exc:
        raise MarketQualityBlocked("OBSERVATION_CLOCK_INVALID") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise MarketQualityBlocked("OBSERVATION_CLOCK_NAIVE")
    return dt.astimezone(timezone.utc).isoformat()


def _decimal(v,minimum=None,maximum=None):
    if type(v) not in (str,int,float) or isinstance(v,bool):
        raise MarketQualityBlocked("VALUE_WRONG_TYPE")
    try:
        n=Decimal(str(v))
    except (InvalidOperation,ValueError) as exc:
        raise MarketQualityBlocked("VALUE_WRONG_TYPE") from exc
    if not n.is_finite() or (minimum is not None and n<minimum) or (
            maximum is not None and n>maximum):
        raise MarketQualityBlocked("VALUE_OUT_OF_ACCEPTED_CONTEXT")
    return n


def integrate_market_quality(mf: dict, nav: dict, macro: dict) -> dict:
    if any(not isinstance(x,dict) for x in (mf,nav,macro)):
        raise MarketQualityBlocked("SOURCE_EVIDENCE_OBJECT_REQUIRED")
    if (mf.get("schema")!="ISL_MF_SECONDARY_MARKET_TURNOVER_HISTORY_V07"
            or mf.get("unique_month_count")!=202
            or mf.get("last_month")!="2026-09"
            or mf.get("first_month")!="2009-12"
            or mf.get("historical_pit_first_publication_certified") is not False
            or mf.get("tradable_bond_total_return_series_qualified") is not False
            or mf.get("unit")!="MILLION_PLN_TURNOVER_NOT_PRICE_OR_TOTAL_RETURN"):
        raise MarketQualityBlocked("MF_ORIGINAL_MONTHLY_LIQUIDITY_CONTEXT_INVALID")
    if (nav.get("schema")!="ISL_UKNF_HISTORICAL_PRIMARY_UNIT_SAMPLE_V06"
            or nav.get("daily_same_class_observations")!=22
            or nav.get("first_observation_day")!="2026-09-01"
            or nav.get("last_observation_day")!="2026-09-30"
            or nav.get("selected_currency")!="PLN"
            or nav.get("selected_primary_share_class") is not True
            or nav.get("historical_pit_certified") is not False
            or nav.get("fund_holding_period_total_return_qualified") is not False):
        raise MarketQualityBlocked("NAV_ORIGINAL_SHARE_CLASS_CONTEXT_INVALID")
    if (macro.get("schema")!="ISL_PUBLIC_MULTISOURCE_MACRO_EVIDENCE_V05"
            or macro.get("joint_reference_month")!="2026-09"
            or macro.get("nbp_observed_business_days")!=22
            or macro.get("hicp_months")!=13
            or macro.get("government_yield_months")!=59
            or macro.get("historical_point_in_time_certified") is not False
            or macro.get("asset_total_return_series_qualified")!=[]
            or macro.get("source_rights_fully_approved") is not False):
        raise MarketQualityBlocked("MACRO_ORIGINAL_SOURCE_WINDOW_INCOMPATIBLE")
    # A KID for another fund/class must never be attached.
    if nav.get("kid_exact_fund_unit_currency_match") is False:
        if (nav.get("kid_risk_level_descriptive_not_recommendation") is not None
                or any(x is not None for x in (
                    nav.get("kid_stated_costs_rates_not_actual_fees") or {}).values())):
            raise MarketQualityBlocked("KID_ANOTHER_FUND_CONTAMINATED_NAV")
    for x in (mf,nav,macro):
        if x.get("financial_operations")!=0 or x.get("database_writes")!=0:
            raise MarketQualityBlocked("SOURCE_FINANCIAL_OPERATION_GUARD_FAILED")
    clocks={
        "mf":_utc(mf.get("source_observed_at_utc")),
        "nav":_utc(nav.get("observed_at_utc")),
        "macro":_utc(macro.get("observed_at_utc")),
    }
    fingerprints={
        "mf_original_workbook":_sha(mf.get("source_sha256")),
        "uknf_same_unit_nav":_sha(nav.get("source_documents",{}).get("history_sha256")),
        "nbp_eurostat_joined_reference":_sha(
            macro.get("nbp_eurostat_joint_source_receipt_sha256")),
        "eurostat_10y_yield":_sha(macro.get("yield_original_source_sha256")),
    }
    mf_share=mf.get("latest_month_channel_shares_pct")
    if not isinstance(mf_share,dict) or set(mf_share)!={"interbank","bondspot","gpw"}:
        raise MarketQualityBlocked("MF_CHANNEL_SHARE_SHAPE_INVALID")
    share=sum((_decimal(v,minimum=Decimal(0),maximum=Decimal(100))
               for v in mf_share.values()),Decimal(0))
    if abs(share-Decimal(100))>Decimal("0.02"):
        raise MarketQualityBlocked("MF_SHARE_DENOMINATOR_INCOHERENT")
    nav_delta=_decimal(nav.get("observed_nav_level_change_pct_not_total_return"),
                       minimum=Decimal("-100"),maximum=Decimal("100000"))
    nominal_yield=_decimal(macro.get("pl_nominal_10y_government_yield_pct_per_annum"),
                           minimum=Decimal("-20"),maximum=Decimal("50"))
    inflation=_decimal(macro.get("pl_trailing_12m_hicp_inflation_pct"),
                       minimum=Decimal("-20"),maximum=Decimal("150"))
    macro_gap=_decimal(macro.get("arithmetic_yield_minus_trailing_inflation_pp"),
                       minimum=Decimal("-200"),maximum=Decimal("200"))
    if abs((nominal_yield-inflation)-macro_gap)>Decimal("0.0002"):
        raise MarketQualityBlocked("MACRO_GAP_ARITHMETIC_DOES_NOT_RECONCILE")
    mf_total=_decimal(mf.get("latest_total_mln_pln"),minimum=Decimal(0))
    if abs(mf_total-Decimal("3140385.25"))>Decimal("0.1"):
        raise MarketQualityBlocked("MF_PUBLISHED_2026_SEPT_TOTAL_NOT_RECONCILED")
    report={
        "schema":SCHEMA,
        "state":"CROSS_SOURCE_DESCRIPTIVE_QUALITY_NOT_INVESTMENT_DECISION",
        "aligned_observation_month":"2026-09",
        "data_grains":{
            "mf":"CALENDAR_MONTH_MARKET_TURNOVER_MLN_PLN",
            "uknf":"DAILY_PRIMARY_UNIT_NAV_PLN_SINGLE_FUND",
            "nbp":"DAILY_REFERENCE_FX_AND_GOLD_QUOTATIONS",
            "eurostat":"MONTHLY_HICP_AND_ANNUALIZED_NOMINAL_GOV_YIELD_LEVEL",
        },
        "original_source_observed_at_utc":clocks,
        "original_source_payload_fingerprints":fingerprints,
        "historical_first_publication_vintages_proven":False,
        "same_source_retrieval_instant":len(set(clocks.values()))==1,
        "cross_source_causal_inference_permitted":False,
        "cross_source_return_correlation_calculated":False,
        "licensed_bond_index_benchmarks_admitted":False,
        "source_quality_gate":{
            "mf_complete_history_months":mf["unique_month_count"],
            "uknf_same_primary_class_nav_days":nav["daily_same_class_observations"],
            "uknf_kid_exact_asof_match":nav.get("kid_exact_fund_unit_currency_match") is True,
            "macro_nbp_publication_days":macro["nbp_observed_business_days"],
            "macro_hicp_months":macro["hicp_months"],
            "macro_10y_yield_months":macro["government_yield_months"],
        },
        "context_only":{
            "mf_latest_total_mln_pln":str(mf_total),
            "mf_interbank_share_pct":mf_share["interbank"],
            "mf_bondspot_share_pct":mf_share["bondspot"],
            "mf_gpw_share_pct":mf_share["gpw"],
            "uknf_primary_unit_nav_change_pct_NOT_total_return":str(nav_delta),
            "eurostat_nominal_10y_yield_percent_pa_NOT_bond_return":str(nominal_yield),
            "eurostat_trailing12m_hicp_pct":str(inflation),
            "arithmetic_yield_level_minus_prior_inflation_pp_NOT_real_return":str(macro_gap),
        },
        "model_trading_qualification":[],
        "m1_m2_m3":"INSUFFICIENT_DATA_HOLD_CASH",
        "portfolio_positions_queried":0,
        "accounts_connected":0,
        "orders_sent":0,
        "financial_operations":0,
        "database_writes":0,
        "scheduled_sources_created":0,
    }
    report["receipt_sha256"]=sha256(
        json.dumps(report,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return report
