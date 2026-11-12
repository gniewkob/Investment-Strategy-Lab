"""Public-first NBP reference comparisons with official Poland HICP context.

Retrospective macro arithmetic ONLY. NBP gold PLN/gram and Table A mid FX are
not executable prices. Eurostat HICP is a price-level index, not an asset.
No source response from today authenticates historic point-in-time vintages.
No accounts, network by default, DB, orders or cash movement of any kind.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import json
from typing import Callable

from scripts.nbp_reference_capture import _fetch as _nbp_fetch
from scripts.public_first_nbp_reference_research_v01 import (
    PublicReferenceBlocked, official_fetch as official_nbp_fetch,
    research_public_nbp,
)
from scripts.eurostat_hicp_macro_context_v01 import (
    HICPContextError, _fetch as fetch_eurostat,
    _query as eurostat_url, inspect_hicp,
)

D = Decimal
SCHEMA = "ISL_PUBLIC_FIRST_HICP_NBP_PURCHASING_POWER_V01"
MAX_MONTHS = 59


class PurchasingPowerBlocked(ValueError):
    """Source publication or semantic alignment makes the research unsafe."""


def _money(value: Decimal) -> str:
    return format(value.quantize(D("0.01")), "f")


def _amount(value: object) -> Decimal:
    if not isinstance(value, str):
        raise PurchasingPowerBlocked("INVALID_HICP_LEVEL")
    try:
        number = D(value)
    except (InvalidOperation, ValueError) as exc:
        raise PurchasingPowerBlocked("INVALID_HICP_LEVEL") from exc
    if not number.is_finite() or number <= 0:
        raise PurchasingPowerBlocked("INVALID_HICP_LEVEL")
    return number


def public_purchasing_power_research(
    *, since: str = "2021-11", until: str = "2026-09",
    nbp_fetch: Callable[[str], bytes] | None = None,
    hicp_payload: object = None,
    today: date | None = None,
    clock=None,
) -> dict:
    """Match exactly the published months; refuse missing HICP releases.

    `inflation_matched_contribution_reference_pln` is the end-month price
    level equivalent of separate, nominal 100 PLN contributions each month.
    It is NOT cash invested, an obtainable inflation hedge, or a future P&L.
    """
    if nbp_fetch is None or hicp_payload is None:
        raise PurchasingPowerBlocked("EXPLICIT_PUBLIC_SOURCE_INPUTS_REQUIRED")
    try:
        nbp = research_public_nbp(
            since, until, fetch=nbp_fetch, today=today, clock=clock)
        hicp = inspect_hicp(
            hicp_payload, since=since, until=until,
            retrieval_scope="EUROSTAT_PUBLIC_READ_ONLY")
    except (PublicReferenceBlocked, HICPContextError) as exc:
        raise PurchasingPowerBlocked("OFFICIAL_SOURCE_CONTRACT_REJECTED") from exc
    months = nbp["complete_months"]
    if (months > MAX_MONTHS or months < 12 or
            hicp.get("status") != "AVAILABLE_CONTEXT_NOT_HISTORICAL_PIT" or
            hicp.get("observed_month_count") != months or
            hicp.get("available_month_count") != months or
            hicp.get("missing_months") or
            hicp.get("country") != "PL" or
            hicp.get("measure_unit") != "I25_INDEX_2025_100" or
            hicp.get("dataflow_semantics") != "ECOICOP_V2_ALL_ITEMS_HICP" or
            hicp.get("historical_point_in_time_certified") is not False or
            hicp.get("price_index_as_asset_return") is not False):
        raise PurchasingPowerBlocked("INCOMPLETE_OR_WRONGLY_TYPED_HICP")
    observations = hicp["observations"]
    if len(observations) != months or not isinstance(observations, list):
        raise PurchasingPowerBlocked("HICP_MONTHS_MISALIGNED")
    aligned = nbp["monthly_selected_dates"]
    if set(aligned) != {"gold", "usdpln", "eurpln"}:
        raise PurchasingPowerBlocked("NBP_ASSET_TYPES_CHANGED")
    expected = [date.fromisoformat(s[:7] + "-01").strftime("%Y-%m")
                for s in aligned["gold"]]
    if (len(expected) != months or len(set(expected)) != months or
            expected[0] != since or expected[-1] != until or
            any(len(aligned[k]) != months for k in aligned)):
        raise PurchasingPowerBlocked("NBP_CALENDAR_MISMATCH")
    if any(date.fromisoformat(day).strftime("%Y-%m") != ym
           for key in aligned for day, ym in zip(aligned[key], expected)):
        raise PurchasingPowerBlocked("NBP_MONTHS_MISALIGNED")
    if any(obs.get("month") != ym for obs, ym in zip(observations, expected)):
        raise PurchasingPowerBlocked("HICP_MONTHS_MISALIGNED")
    if not isinstance(nbp.get("scenarios"), list) or len(nbp["scenarios"]) != 7:
        raise PurchasingPowerBlocked("NBP_SCENARIOS_CHANGED")
    with localcontext() as ctx:
        ctx.prec = 45
        levels = [_amount(row["index_2025_100"]) for row in observations]
        end_level = levels[-1]
        start_level = levels[0]
        hypothetic_nominal = D("100") * D(months)
        # Same cashflow calendar as the reference cases: each hypothetical
        # contribution's equivalent nominal amount at the last HICP level.
        inflation_baseline = sum(
            (D("100") * end_level / value for value in levels), D("0"))
        result_rows = []
        for case in nbp["scenarios"]:
            if (case.get("executable_asset") is not False or
                    case.get("virtual_contributions_pln") !=
                    _money(hypothetic_nominal) or
                    case.get("assumed_one_way_cost_bps") not in ("0", "30")):
                raise PurchasingPowerBlocked("NBP_SCENARIO_SEMANTICS_CHANGED")
            terminal = _amount(case.get("terminal_reference_value_pln"))
            result_rows.append({
                "code": case["code"],
                "reference_kind": case["source_kind"],
                "assumed_one_way_cost_bps": case["assumed_one_way_cost_bps"],
                "nominal_terminal_reference_pln": _money(terminal),
                "hypothetical_nominal_contributions_pln":
                    _money(hypothetic_nominal),
                "nominal_difference_vs_contributions_pln":
                    _money(terminal - hypothetic_nominal),
                "difference_vs_cpi_matched_cashflows_pln":
                    _money(terminal - inflation_baseline),
                "not_executable_or_predicted": True,
            })
        if (len(result_rows) != 7 or
                any(z["not_executable_or_predicted"] is not True
                    for z in result_rows)):
            raise PurchasingPowerBlocked("NON_EXECUTABLE_SCENARIO_REQUIRED")
        price_level_delta = (end_level / start_level - D("1")) * D("100")
    evidence = {
        "schema": SCHEMA,
        "status": "PUBLIC_MACRO_REFERENCE_CONTEXT_ONLY",
        "source": "Eurostat prc_hicp_minr, PL / M / TOTAL / I25",
        "nbp_sources": ["NBP gold PLN/g", "NBP Table A USDPLN and EURPLN"],
        "source_attribution": "Source: Eurostat, prc_hicp_minr; NBP, api.nbp.pl",
        "first_month": since, "last_month": until,
        "aligned_published_months": months,
        "eurostat_index_reference_base": "2025=100, COICOP 2018",
        "source_eurostat_updated": hicp["provider_reported_last_update"],
        "source_eurostat_canonical_sha256":
            hicp["source_payload_canonical_sha256"],
        "source_nbp_monthly_values_canonical_sha256":
            nbp["monthly_values_canonical_sha256"],
        "source_nbp_raw_sha256_receipts": nbp["raw_source_receipts"],
        "historical_first_release_captured": False,
        "historical_point_in_time_certified": False,
        "historical_nbpxfx_mid_not_executable": True,
        "gold_reference_is_price_only_not_total_return": True,
        "hicp_is_macro_context_not_asset_return": True,
        "source_eurostat_first_published_asof_verified": False,
        "consumer_price_index_change_pct": _money(price_level_delta),
        "cpi_matched_hypothetical_monthly_cashflows_pln":
            _money(inflation_baseline),
        "hypothetical_nominal_contributions_pln":
            _money(hypothetic_nominal),
        "scenarios": result_rows,
        "legacy_m1_m2_m3": "NOT_RUN_UNQUALIFIED_TOTAL_RETURN_SERIES",
        "qualified_model_series": [],
        "orders_sent": 0, "paper_events_created": 0,
        "database_connections": 0, "database_writes": 0,
        "financial_operations": 0, "investment_profit_proven": False,
        "warning": (
            "Retrospective CPI vs non-executable reference-unit comparison "
            "only; prices, FX spreads and trade fills not available. Eurostat "
            "2025=100 levels are the latest re-referenced data, not the "
            "historical release versions. CPI-matched monthly cashflows are "
            "a methodological comparator, NOT an investable security."
        ),
    }
    digestable = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    evidence["receipt_sha256"] = sha256(digestable.encode("utf-8")).hexdigest()
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default="2021-11")
    parser.add_argument("--until", default="2026-09")
    parser.add_argument("--allow-public-source-fetch", action="store_true")
    args = parser.parse_args()
    if not args.allow_public_source_fetch:
        parser.error("explicit --allow-public-source-fetch required")
    try:
        payload = fetch_eurostat(eurostat_url(args.since, args.until))
        result = public_purchasing_power_research(
            since=args.since, until=args.until,
            nbp_fetch=official_nbp_fetch, hicp_payload=payload)
    except (PurchasingPowerBlocked, HICPContextError, OSError, ValueError) as exc:
        parser.error("PUBLIC_FIRST_HICP_RESEARCH_FAILED: " + str(exc))
    # Raw historical values are not logged; receipts and aggregates only.
    print("ISL_PUBLIC_FIRST_HICP_NBP_RECEIPT=" +
          json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
