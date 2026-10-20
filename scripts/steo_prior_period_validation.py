"""Predeclared 2022-2023 historical EIA STEO stress set, research-only.

Official 24 monthly release dates transcribed from EIA original STEO index.
Keep this separate from the preexisting verified 34-release 2024-2026 study.
Additional Jan-Aug 2024 editions are a REFERENCE-ONLY bridge to evaluate all
late-2023 target-month forecasts, not part of the holdout forecasts or tuning.
No transactions, databases or user secrets.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
import hashlib
import json
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from scripts.steo_historical_archive import BASE, INDEX, MONTHS, SIZE_LIMIT, catalog, inspect_xlsx, retrieve
from scripts.steo_monthly_forecast_eval import compare_editions, parse_edition
from src.isl_v2.eia_sources import SourceFormatError

PRIOR_DAYS = {
    2022: (11, 8, 8, 12, 10, 7, 12, 9, 7, 12, 8, 6),
    2023: (10, 7, 7, 11, 9, 6, 11, 8, 12, 11, 7, 12),
}


def prior_catalog() -> dict:
    items={}
    for year, days in PRIOR_DAYS.items():
        for index, day in enumerate(days, 1):
            issue=f"{MONTHS[index-1]}{str(year)[-2:]}"
            items[issue]={
                "issue":issue,
                "official_release_day":f"{year:04d}-{index:02d}-{day:02d}",
                "xlsx_url":BASE+issue+"_base.xlsx",
                "pdf_url":BASE+issue+".pdf",
                "official_index_url":INDEX,
                "release_precision":"DAY",
                "historical_original_bytes_certified":False,
            }
    return items


def retrieve_prior(issue: str, opener=urlopen) -> tuple[bytes, str]:
    c=prior_catalog()
    if issue not in c:
        raise SourceFormatError("Earlier historical STEO issue not allowlisted")
    target=c[issue]["xlsx_url"]
    req=Request(target, headers={"User-Agent":"ISL-STEO-Earlier-Validation/1.0"})
    with opener(req,timeout=30) as r:
        final=r.geturl()
        parsed=urlparse(final)
        if (parsed.scheme!="https" or parsed.netloc!="www.eia.gov"
                or parsed.path!="/outlooks/steo/archives/"+issue+"_base.xlsx"
                or parsed.query or parsed.fragment):
            raise SourceFormatError("Earlier STEO archive URL outside official allowlist")
        data=r.read(SIZE_LIMIT+1)
    inspect_xlsx(data)
    return data,final


def fixed_rule_prior_period_report(prior_editions: list[dict], bridge_editions: list[dict]) -> dict:
    """Freeze MAE comparisons; no hyperparameter tuning, no future-source use.

    Every 2022-23 issued forecast is compared to the earliest sampled later
    historical STEO reported value at least two months after target. The 2024
    bridge can supply reference outcomes only; it must not enter prior
    forecast sample or become a learned or optimized model.
    """
    permitted=prior_catalog()
    bridge_codes=list(catalog())[:8]
    if (len(prior_editions)!=24 or len(bridge_editions)!=8 or
            {x["issue"] for x in prior_editions}!=set(permitted) or
            [x["issue"] for x in bridge_editions]!=bridge_codes):
        raise SourceFormatError("Fixed 24-issue prior historical period and reference bridge required")
    if any(x["official_release_day"]!=permitted[x["issue"]]["official_release_day"]
           or x.get("original_first_release_bytes_certified") is not False
           for x in prior_editions):
        raise SourceFormatError("Wrong independent earlier release chronology or original-byte claim")
    result=compare_editions(prior_editions+bridge_editions)
    prior_pairs=[x for x in result["paired_records"]
                 if x["forecast_edition"] in permitted]
    if len(prior_pairs)!=144:
        raise SourceFormatError("Predeclared 24x2x3 past forecast cohort incomplete")
    by_group=defaultdict(list)
    for row in prior_pairs:
        by_group[(row["instrument_code"],row["horizon_calendar_months"])].append(row)
    if len(by_group)!=6 or any(len(x)!=24 for x in by_group.values()):
        raise SourceFormatError("Source/horizon historical holdout missing pairs")
    groups=[]
    for (inst,h),pairs in sorted(by_group.items()):
        by_year={}
        for year in ("2022","2023"):
            group=[x for x in pairs if x["edition_release_day"].startswith(year)]
            if len(group)!=12:
                raise SourceFormatError("Holdout must contain 12 forecasts for each year")
            def mean(k):
                return str((sum((Decimal(x[k]) for x in group),Decimal("0"))/
                            len(group)).quantize(Decimal("0.01")))
            by_year[year]={
                "forecast_count":len(group),
                "eia_mae_usd_bbl":mean("absolute_source_forecast_error"),
                "naive_mae_usd_bbl":mean("absolute_naive_error"),
                "source_EIA_win_count":sum(
                    Decimal(x["absolute_source_forecast_error"])<
                    Decimal(x["absolute_naive_error"]) for x in group),
            }
        def mean_all(k):
            return str((sum((Decimal(x[k]) for x in pairs),Decimal("0"))/
                        len(pairs)).quantize(Decimal("0.01")))
        ea=mean_all("absolute_source_forecast_error")
        na=mean_all("absolute_naive_error")
        groups.append({
            "instrument_code":inst,
            "horizon_months":h,
            "n_forecast_issues":24,
            "eia_mae_usd_bbl":ea,
            "naive_mae_usd_bbl":na,
            "source_EIA_lower_mae":Decimal(ea)<Decimal(na),
            "by_year":by_year,
        })
    return {
        "status":"STEO_PREDECLARED_EARLIER_2022_2023_HISTORICAL_SOURCE_VALIDATION",
        "prior_editions":24,
        "reference_only_bridge_editions":8,
        "original_old_era_forecast_pairs":len(prior_pairs),
        "reference_policy":result["reference_policy"],
        "prior_period_test_rule":"FROZEN_ALWAYS_EIA_VS_SAME_OLD_EDITION_PREVIOUS_MONTH_NAIVE",
        "heldout_period_is_chronologically_future":False,
        "historical_original_publication_bytes_certified":False,
        "source_prices_are_tradable_returns":False,
        "predictive_investment_advantage_established":False,
        "by_source_horizon":groups,
        "database_connections":0,"database_writes":0,
        "real_orders":0,"paper_allocations_changed":0,
        "schedule_enabled":False,
        "source_workbooks_persisted":0,
    }
