"""Integrated public-first source bundle: NBP + Eurostat + exchange rights.

Public official macro reference only: no historic PIT, market-data license
grant, equity/bond total-return admission, investor advice or execution.
One explicitly authorized, bounded, one-shot read of four fixed HTTPS URLs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import json
from typing import Callable

from scripts.nbp_reference_capture import capture
from scripts.public_first_nbp_reference_research_v01 import official_fetch
from scripts.eurostat_hicp_macro_context_v01 import (
    _fetch as official_hicp_fetch, _query as hicp_query, inspect_hicp,
)
from scripts.eurostat_pl_bond_yield_source_probe_v04 import (
    fetch_official as official_yield_fetch, URL as YIELD_URL,
)
from scripts.eurostat_pl_government_bond_yield_context_v04 import (
    parse_original_yields,
)
from scripts.public_first_prospective_source_observation_v03 import (
    assemble_receipt,
)

SCHEMA = "ISL_PUBLIC_MULTISOURCE_MACRO_EVIDENCE_V05"
NBP_START, NBP_END = "2026-09-01", "2026-09-30"
HICP_SINCE, HICP_UNTIL = "2025-09", "2026-09"
YIELD_SINCE, YIELD_UNTIL = "2021-11", "2026-09"

# Source metadata and rights statuses, not live access tokens or model grants.
SOURCE_QUEUE = (
    {
        "id": "BONDSPOT_TBSP_INDEX",
        "official_url": "https://www.bondspot.pl/tbsp_index_archiwum",
        "publisher": "BondSpot / GPW Benchmark",
        "data_kind": "POLISH_GOV_BOND_BENCHMARK_INDEX_LEVEL",
        "state": "PUBLIC_EXCHANGE_ARCHIVE_RIGHTS_AND_PIT_BLOCKED",
        "rights_url": "https://www.bondspot.pl/1303",
        "automated_ingestion_authorized": False,
        "historic_first_published_proven": False,
        "asset_total_return_qualified": False,
    },
    {
        "id": "GPW_STOCK_INDEX_HISTORY",
        "official_url": "https://www.gpw.pl/archiwum-notowan",
        "publisher": "GPW / GPW Benchmark",
        "data_kind": "EQUITY_INDEX_HISTORY_CHANNEL_UNQUALIFIED",
        "state": "PUBLIC_EXCHANGE_EXPORT_RIGHTS_AND_INDEX_SEMANTICS_BLOCKED",
        "rights_url": "https://gpwbenchmark.pl/zastrzezenia-prawne",
        "automated_ingestion_authorized": False,
        "historic_first_published_proven": False,
        "asset_total_return_qualified": False,
    },
    {
        "id": "VANGUARD_ALL_WORLD_ACC_NAV_USD",
        "official_url": "https://www.pl.vanguard/inwestorzy-indywidualni/produkt/etf/akcje/9679/ftse-all-world-ucits-etf-usd-accumulating",
        "publisher": "Vanguard",
        "data_kind": "FUND_SHARE_CLASS_NET_ASSET_VALUE_NOT_EXECUTABLE_PRICE",
        "state": "PRIVATE_ORIGINAL_FILE_VERIFIED_RIGHTS_PIT_BLOCKED",
        "rights_url": "https://www.vanguard.co.uk/professional/terms-and-conditions",
        "automated_ingestion_authorized": False,
        "historic_first_published_proven": False,
        "asset_total_return_qualified": False,
    },
    {
        "id": "SWINKELS_GOV_BOND_2020_2022",
        "official_url": "https://doi.org/10.34894/YWT2IX",
        "publisher": "Laurens Swinkels / DataverseNL",
        "data_kind": "HISTORIC_MODELED_NON_POLISH_BOND_HOLDING_PERIOD_RETURN",
        "state": "CC_BY_HISTORIC_RESEARCH_NOT_POLISH_TR_OR_CURRENT_PIT",
        "rights_url": "https://creativecommons.org/licenses/by/4.0/",
        "automated_ingestion_authorized": False,
        "historic_first_published_proven": False,
        "asset_total_return_qualified": False,
    },
)


class MultiSourceBlocked(ValueError):
    """One source failed validation; do not produce a partial success."""


def _decimal(value: object, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or type(value) not in (str, int, float):
        raise MultiSourceBlocked("NONFINITE_OR_INVALID_SOURCE_NUMBER")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise MultiSourceBlocked("NONFINITE_OR_INVALID_SOURCE_NUMBER") from exc
    if not number.is_finite() or (positive and number <= 0):
        raise MultiSourceBlocked("NONFINITE_OR_INVALID_SOURCE_NUMBER")
    return number


def _utc(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise MultiSourceBlocked("UTC_AWARE_CLOCK_REQUIRED")
    return value.astimezone(timezone.utc)


def _canonical(data: object) -> bytes:
    return json.dumps(data, separators=(",", ":"), sort_keys=True).encode()


def _sep2026_bond_yield(yield_raw: bytes) -> Decimal:
    """After the v0.4 typed source validator: 1×1×1×59, all dimensions fixed."""
    payload = json.loads(yield_raw)
    ids = payload["id"]
    cats = payload["dimension"]["time"]["category"]["index"]
    position = cats[YIELD_UNTIL]
    coordinates = [position if k == "time" else 0 for k in ids]
    offset = 0
    for coordinate, size in zip(coordinates, payload["size"]):
        offset = offset * size + coordinate
    values = payload["value"]
    value = (values[offset] if isinstance(values, list)
             else values.get(str(offset)))
    number = _decimal(value)
    if not Decimal("-20") <= number <= Decimal("50"):
        raise MultiSourceBlocked("YIELD_UNIT_NOT_PERCENT_PER_ANNUM")
    return number


def evaluate_combined_sources(nbp: object, hicp: object, yield_raw: bytes, *,
                              completed_at: datetime) -> dict:
    """In-memory source-receipt reconciliation; no external calls."""
    clock = _utc(completed_at)
    if clock.date().isoformat() < NBP_END or clock.strftime("%Y-%m") < YIELD_UNTIL:
        raise MultiSourceBlocked("FUTURE_SOURCE_WINDOW")
    yield_report = parse_original_yields(yield_raw, observed_at=clock)
    joint = assemble_receipt(
        nbp, hicp, nbp_start=NBP_START, nbp_end=NBP_END,
        hicp_since=HICP_SINCE, hicp_until=HICP_UNTIL, completed_at=clock)
    if (yield_report.get("observed_months") != 59
            or yield_report.get("last_month") != YIELD_UNTIL
            or yield_report.get("country") != "PL"
            or yield_report.get("source_unit") != "PERCENT_PER_ANNUM"
            or yield_report.get("historical_pit_certified") is not False
            or joint.get("historical_pit_certified") is not False
            or any(yield_report.get(key) != 0 for key in
                   ("financial_operations", "database_writes", "orders_sent"))):
        raise MultiSourceBlocked("WRONG_OR_UNQUALIFIED_SOURCE")
    observations = hicp["observations"]
    if (len(observations) != 13
            or observations[0].get("month") != HICP_SINCE
            or observations[-1].get("month") != HICP_UNTIL
            or joint.get("eurostat_observation_months") != 13):
        raise MultiSourceBlocked("HICP_13_MONTH_BASELINE_REQUIRED")
    with localcontext() as ctx:
        ctx.prec = 40
        before = _decimal(observations[0]["index_2025_100"], positive=True)
        now = _decimal(observations[-1]["index_2025_100"], positive=True)
        trailing_hicp_pct = (now / before - Decimal("1")) * Decimal("100")
        nominal_yield_pct = _sep2026_bond_yield(yield_raw)
        gap_pp = nominal_yield_pct - trailing_hicp_pct
    if len(nbp["series"]["gold"]) != len(nbp["series"]["usdpln"]) or (
            len(nbp["series"]["gold"]) != len(nbp["series"]["eurpln"])):
        raise MultiSourceBlocked("NBP_SOURCE_SERIES_MISALIGNED")
    # NBP gold and FX are reference quotations, not custody/market fills.
    if any(
        [row["publication_date"] for row in nbp["series"][kind]] !=
        [row["publication_date"] for row in nbp["series"]["gold"]]
        for kind in ("usdpln", "eurpln")
    ):
        raise MultiSourceBlocked("NBP_PUBLICATION_DATES_NOT_IDENTICAL")
    report = {
        "schema": SCHEMA,
        "state": "PUBLIC_FIRST_JOINT_MACRO_RESEARCH_ONLY",
        "observed_at_utc": clock.isoformat(),
        "source_families": ["NBP", "Eurostat HICP", "Eurostat PL government yield"],
        "series_types": {
            "nbp_usdpln": "TABLE_A_MID_FX_REFERENCE",
            "nbp_eurpln": "TABLE_A_MID_FX_REFERENCE",
            "nbp_gold": "GOLD_PRICE_PLN_PER_GRAM",
            "hicp_pl": "CONSUMER_PRICE_INDEX_I25",
            "pl_government_10y": "NOMINAL_YIELD_PERCENT_PER_ANNUM_NOT_BOND_RETURN",
        },
        "nbp_observed_business_days": len(nbp["series"]["gold"]),
        "nbp_reference_window": [NBP_START, NBP_END],
        "hicp_months": 13,
        "hicp_window": [HICP_SINCE, HICP_UNTIL],
        "government_yield_months": 59,
        "government_yield_window": [YIELD_SINCE, YIELD_UNTIL],
        "joint_reference_month": YIELD_UNTIL,
        "pl_nominal_10y_government_yield_pct_per_annum": str(nominal_yield_pct),
        "pl_trailing_12m_hicp_inflation_pct": format(trailing_hicp_pct.quantize(Decimal("0.0001")), "f"),
        "arithmetic_yield_minus_trailing_inflation_pp": format(gap_pp.quantize(Decimal("0.0001")), "f"),
        "gap_semantics": "DESCRIPTIVE_LEVEL_MINUS_BACKWARD_LOOKING_PRICE_INDEX_CHANGE_NOT_REAL_YIELD_RETURN_OR_FORECAST",
        "nbp_eurostat_joint_source_receipt_sha256": joint["receipt_sha256"],
        "yield_original_source_sha256": yield_report["original_response_sha256"],
        "source_fingerprints_sha256": {
            **joint["source_fingerprints_sha256"],
            "eurostat_pl_government_yield": yield_report["original_response_sha256"],
        },
        "external_exchange_source_queue": [dict(x) for x in SOURCE_QUEUE],
        "exchange_licensed_bulk_source_approved": False,
        "historical_point_in_time_certified": False,
        "source_rights_fully_approved": False,
        "asset_total_return_series_qualified": [],
        "m1_m2_m3": "INSUFFICIENT_DATA_HOLD_CASH",
        "financial_operations": 0,
        "account_connections": 0,
        "database_writes": 0,
        "paper_events_created": 0,
        "orders_sent": 0,
    }
    report["receipt_sha256"] = sha256(_canonical(report)).hexdigest()
    return report


def observe_once(*, nbp_fetch: Callable | None, hicp_fetch: Callable | None,
                 yield_fetch: Callable | None,
                 clock: Callable = lambda: datetime.now(timezone.utc)) -> dict:
    if nbp_fetch is None or hicp_fetch is None or yield_fetch is None:
        raise MultiSourceBlocked("EXPLICIT_PUBLIC_SOURCE_FETCH_REQUIRED")
    # Validate clock before opening any network connection.
    started = _utc(clock())
    if started.date().isoformat() < NBP_END:
        raise MultiSourceBlocked("FUTURE_SOURCE_WINDOW")
    nbp = capture(NBP_START, NBP_END, fetch=nbp_fetch, clock=clock)
    hicp = inspect_hicp(
        hicp_fetch(hicp_query(HICP_SINCE, HICP_UNTIL)),
        since=HICP_SINCE, until=HICP_UNTIL,
        retrieval_scope="EUROSTAT_PUBLIC_READ_ONLY")
    # Yield fetch is explicitly injected; official implementation has fixed URL.
    raw = yield_fetch()
    return evaluate_combined_sources(nbp, hicp, raw, completed_at=clock())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-public-official-fetch", action="store_true")
    args = parser.parse_args()
    if not args.allow_public_official_fetch:
        parser.error("Explicit --allow-public-official-fetch is required")
    report = observe_once(
        nbp_fetch=official_fetch, hicp_fetch=official_hicp_fetch,
        yield_fetch=official_yield_fetch)
    # No per-day NBP observations or 59-row Eurostat source vectors.
    print("ISL_PUBLIC_MULTISOURCE_CONTEXT=" +
          json.dumps(report, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
