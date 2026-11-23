"""Historical POLSTR CI versus HICP purchasing-power reference (not trading).

Four bounded original GPW Benchmark PDFs and one Eurostat JSON-stat response.
No historical publication-vintage certification, DB writes, or real orders.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable

from scripts.eurostat_hicp_macro_context_v01 import (
    HICPContextError, _fetch as official_hicp_fetch, _query as hicp_url,
    inspect_hicp,
)
from scripts.polstr_cash_reference_v10 import (
    MONTHS, OFFICIAL_PDF_URL, POLSTR_YEARS, PolstrReferenceBlocked,
    _extract_pdf_text, _official_fetch as official_pdf_fetch,
    indexed_contribution_reference, inspect_official_year,
)

SCHEMA = "ISL_POLSTR_CI_HICP_PURCHASING_POWER_V11"
FIRST, LAST = MONTHS[0], MONTHS[-1]
PLN = Decimal("100")


class ReferenceBlocked(ValueError):
    """Incomplete or inconsistent original source: do not emit a comparison."""


def _clock_utc(clock):
    value = clock()
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ReferenceBlocked("UTC_AWARE_CLOCK_REQUIRED")
    return value.astimezone(timezone.utc)


def _level(value):
    if type(value) is not str:
        raise ReferenceBlocked("POSITIVE_DECIMAL_INDEX_REQUIRED")
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ReferenceBlocked("POSITIVE_DECIMAL_INDEX_REQUIRED") from exc
    if not number.is_finite() or number <= 0:
        raise ReferenceBlocked("POSITIVE_DECIMAL_INDEX_REQUIRED")
    return number


def _two_places(value):
    return format(value.quantize(Decimal("0.01")), "f")


def analyze_once(*, fetch_pdf: Callable[[str], bytes],
                 fetch_hicp: Callable[[str], object],
                 extract_pdf: Callable[[bytes], str] = _extract_pdf_text,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> dict:
    """Validate all 48 paired months in-memory; emit only aggregates and hashes."""
    if not all(callable(x) for x in (fetch_pdf, fetch_hicp, extract_pdf, clock)):
        raise ReferenceBlocked("EXPLICIT_OFFICIAL_SOURCE_ADAPTERS_REQUIRED")
    started = _clock_utc(clock)
    if started.strftime("%Y-%m") <= LAST:
        raise ReferenceBlocked("HISTORICAL_WINDOW_NOT_CLOSED")
    try:
        years = [inspect_official_year(
            fetch_pdf(OFFICIAL_PDF_URL.format(year=y)), year=y,
            extract_text=extract_pdf) for y in POLSTR_YEARS]
        hicp = inspect_hicp(
            fetch_hicp(hicp_url(FIRST, LAST)), since=FIRST, until=LAST,
            retrieval_scope="EUROSTAT_PUBLIC_READ_ONLY")
    except (PolstrReferenceBlocked, HICPContextError, OSError) as exc:
        raise ReferenceBlocked("OFFICIAL_SOURCE_VALIDATION_FAILED") from exc
    polstr = [row for part in years for row in part["month_ends"]]
    prices = hicp.get("observations")
    if (len(polstr) != len(MONTHS)
            or [r["month"] for r in polstr] != list(MONTHS)
            or not isinstance(prices, list) or len(prices) != len(MONTHS)
            or [r.get("month") for r in prices] != list(MONTHS)
            or hicp.get("status") != "AVAILABLE_CONTEXT_NOT_HISTORICAL_PIT"
            or hicp.get("available_month_count") != len(MONTHS)
            or hicp.get("missing_months") != []
            or hicp.get("country") != "PL"
            or hicp.get("measure_unit") != "I25_INDEX_2025_100"
            or hicp.get("dataflow_semantics") != "ECOICOP_V2_ALL_ITEMS_HICP"
            or hicp.get("price_index_as_asset_return") is not False
            or hicp.get("historical_point_in_time_certified") is not False):
        raise ReferenceBlocked("INCOMPLETE_OR_MISALIGNED_REFERENCE_MONTHS")
    index_levels = [_level(r["index_level"]) for r in polstr]
    hicp_levels = [_level(r["index_2025_100"]) for r in prices]
    nominal = indexed_contribution_reference(index_levels)
    with localcontext() as ctx:
        ctx.prec = 48
        reference_exact = sum((PLN * index_levels[-1] / value
                               for value in index_levels), Decimal(0))
        hicp_matched = sum((PLN * hicp_levels[-1] / value
                            for value in hicp_levels), Decimal(0))
        contributions = PLN * len(MONTHS)
        inflation = (hicp_levels[-1] / hicp_levels[0] - 1) * 100
    completed = _clock_utc(clock)
    if completed < started:
        raise ReferenceBlocked("INVALID_COMPLETION_CLOCK")
    report = {
        "schema": SCHEMA,
        "status": "HISTORICAL_NON_EXECUTABLE_INDEX_VS_HICP_CONTEXT_ONLY",
        "first_month": FIRST, "last_month": LAST, "months": len(MONTHS),
        "started_at_utc": started.isoformat(), "completed_at_utc": completed.isoformat(),
        "source_reads": len(years) + 1,
        "sources": ["GPW Benchmark POLSTR_CI annual PDFs", "Eurostat prc_hicp_minr PL M TOTAL I25"],
        "eurostat_source_url": hicp_url(FIRST, LAST),
        "polstr_source_sha256_by_year": {str(x["year"]): x["source_sha256"] for x in years},
        "polstr_daily_observation_counts_by_year": {
            str(x["year"]): x["daily_observation_count"] for x in years},
        "hicp_source_sha256": hicp["source_payload_canonical_sha256"],
        "hicp_source_hash_basis": "CANONICAL_JSON_NOT_ORIGINAL_HTTP_BYTES",
        "hicp_provider_last_updated": hicp["provider_reported_last_update"],
        "preproduction_polstr_months": sum(m < "2025-05" for m in MONTHS),
        "hypothetical_nominal_contributions_pln": _two_places(contributions),
        "polstr_ci_terminal_reference_pln": nominal["terminal_index_reference_pln"],
        "nominal_polstr_difference_vs_contributions_pln": nominal["difference_vs_nominal_cash_pln"],
        "hicp_matched_cashflows_at_end_pln": _two_places(hicp_matched),
        "difference_vs_hicp_matched_cashflows_pln": _two_places(reference_exact - hicp_matched),
        "nominal_cash_shortfall_vs_hicp_pln": _two_places(hicp_matched - contributions),
        "hicp_change_first_to_last_pct": _two_places(inflation),
        "index_vs_cpi_comparison_only": True,
        "historical_point_in_time_certified": False,
        "preproduction_polstr_historical_release_verified": False,
        "first_published_eurostat_vintage_reconciled": False,
        "executable_investment_price": False,
        "investment_performance_proven": False,
        "qualified_total_return_series": [],
        "m1_m2_m3": "INSUFFICIENT_DATA_HOLD_CASH",
        "financial_operations": 0, "database_writes": 0,
        "orders_sent": 0, "paper_events_created": 0,
        "warning": (
            "Retrospective 100 PLN month-end fictional contributions. POLSTR CI "
            "uses month-end index levels, HICP a monthly price-index average; "
            "neither is an executable cash account or investment price. "
            "Index-unit arithmetic excludes fees, taxes and spreads. "
            "2022-2025 reconstructed data do not certify original publication "
            "times; 40 POLSTR months are preproduction. No strategy admission."
        ),
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
    report["receipt_sha256"] = sha256(canonical.encode("utf-8")).hexdigest()
    return report


def render_markdown(report):
    return (
        "# POLSTR CI i HICP — historyczne porównanie siły nabywczej\n\n"
        f"- Okres: {report['first_month']}–{report['last_month']}; {report['months']} miesięcy.\n"
        f"- Wpłaty fikcyjne: {report['hypothetical_nominal_contributions_pln']} PLN.\n"
        f"- Odniesienie POLSTR CI: {report['polstr_ci_terminal_reference_pln']} PLN.\n"
        f"- Wpłaty wyrównane HICP: {report['hicp_matched_cashflows_at_end_pln']} PLN.\n"
        f"- Różnica: {report['difference_vs_hicp_matched_cashflows_pln']} PLN.\n"
        f"- Zmiana HICP pierwszego do ostatniego miesiąca: "
        f"{report['hicp_change_first_to_last_pct']}%.\n\n"
        "**Ograniczenia:** POLSTR CI nie jest depozytem ani instrumentem "
        "transakcyjnym, HICP nie jest stopą zwrotu. HICP opisuje średnią "
        "miesięczną, a POLSTR poziom na koniec miesiąca. Dane rekonstruowane, "
        "w tym 40 miesięcy preprodukcyjnych; nie ma PIT ani kosztów czy podatków.\n\n"
        f"SHA: `{report['receipt_sha256']}`.\n"
    )


def main(argv=None, *, fetch_pdf=official_pdf_fetch,
         fetch_hicp=official_hicp_fetch, extract_pdf=_extract_pdf_text,
         clock=lambda: datetime.now(timezone.utc)):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-public-official-read", action="store_true")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.allow_public_official_read:
        parser.error("EXPLICIT_PUBLIC_SOURCE_READ_OPT_IN_REQUIRED")
    target = args.out_dir
    if target.exists() or target.is_symlink():
        parser.error("OUT_DIR_MUST_NOT_EXIST")
    report = analyze_once(fetch_pdf=fetch_pdf, fetch_hicp=fetch_hicp,
                          extract_pdf=extract_pdf, clock=clock)
    target.mkdir(parents=True, mode=0o700, exist_ok=False)
    with (target / "polstr_hicp_reference_v11.json").open("x", encoding="utf-8") as file:
        json.dump(report, file, sort_keys=True, indent=2, ensure_ascii=False)
        file.write("\n")
    with (target / "polstr_hicp_reference_v11.md").open("x", encoding="utf-8") as file:
        file.write(render_markdown(report))
    print("ISL_POLSTR_HICP_V11=" + json.dumps({
        "status": "PASS_REFERENCE_ONLY", "months": report["months"],
        "source_reads": report["source_reads"],
        "receipt_sha256": report["receipt_sha256"],
        "financial_operations": 0, "database_writes": 0,
    }, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
