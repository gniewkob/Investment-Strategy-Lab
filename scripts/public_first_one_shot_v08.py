"""One-shot official market-source acquisition and v0.7 research report.

Public-only HTTPS, explicitly opted in, fixed bounded source families. Original
MF XLSX and UKNF/NBP/Eurostat responses stay in RAM. The local report contains
only checked aggregate evidence, never raw market files, orders or DB writes.
The resulting research is descriptive, not point-in-time certified or a return.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import json
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError

from scripts.knf_mf_official_source_probe_v06 import MF_URL, fetch_exact
from scripts.knf_original_unit_history_research_v06 import (
    observe_once as observe_knf, official_source_fetch,
)
from scripts.knf_one_class_nav_quality_v07 import describe_unit_nav
from scripts.mf_original_turnover_schema_v07 import inspect_market_sheet
from scripts.mf_bond_turnover_metrics_v07 import analyze_mf_original
from scripts.public_first_multisource_macro_evidence_v05 import (
    observe_once as observe_macro, official_fetch as official_nbp_fetch,
    official_hicp_fetch, official_yield_fetch,
    HICP_SINCE, HICP_UNTIL, _sep2026_bond_yield,
)
from scripts.eurostat_hicp_macro_context_v01 import (
    _query as hicp_query, inspect_hicp, HICPContextError,
)
from scripts.eurostat_pl_government_bond_yield_context_v04 import parse_original_yields
from scripts.nbp_table_a_archive_v09 import (
    ARCHIVE_URL as NBP_FX_ARCHIVE_URL, inspect_archive as inspect_nbp_fx_archive,
    fetch_official as official_nbp_fx_archive_fetch,
)
from scripts.public_first_market_research_v07 import (
    compose_market_research, render_markdown,
)

SCHEMA = "ISL_PUBLIC_FIRST_ONE_SHOT_SOURCE_RUN_V08"
MAX_SOURCE_BYTES = 2_000_000
MAX_READS = {
    "uknf": 4,
    "mf": 1,
    "nbp": 6,
    "nbp_archive_fx": 1,
    "eurostat_hicp": 1,
    "eurostat_yield": 1,
}


class OneShotBlocked(ValueError):
    """Invalid one-shot request or incomplete original-source evidence."""


def _utc(clock: Callable) -> datetime:
    stamp = clock()
    if not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() is None:
        raise OneShotBlocked("UTC_AWARE_CLOCK_REQUIRED")
    return stamp.astimezone(timezone.utc)


def _bytes(raw: object) -> bytes:
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_SOURCE_BYTES:
        raise OneShotBlocked("SOURCE_BYTES_INVALID")
    return raw


def run_once(*, knf_fetch: Callable | None, mf_fetch: Callable | None,
             nbp_fetch: Callable | None, hicp_fetch: Callable | None,
             yield_fetch: Callable | None,
             clock: Callable = lambda: datetime.now(timezone.utc),
             allow_macro_unavailable: bool = False,
             nbp_archive_fetch: Callable | None = None) -> dict:
    """Gather all originals and build a report only if every source validates.

    All network behavior is injected. Callers must explicitly opt in at CLI;
    offline tests can provide synthetic byte readers without any HTTP.
    """
    readers = (knf_fetch, mf_fetch, nbp_fetch, hicp_fetch, yield_fetch)
    if not all(callable(reader) for reader in readers):
        raise OneShotBlocked("EXPLICIT_SOURCE_READERS_REQUIRED")
    started = _utc(clock)  # Reject invalid clocks before any external read.
    counts = dict.fromkeys(MAX_READS, 0)
    attempts = dict.fromkeys(MAX_READS, 0)

    def stamp() -> datetime:
        current = _utc(clock)
        if current < started:
            raise OneShotBlocked("SOURCE_CLOCK_MOVED_BACKWARDS")
        return current

    def read(name: str, source: Callable, *args) -> object:
        if attempts[name] >= MAX_READS[name]:
            raise OneShotBlocked("SOURCE_READ_LIMIT_EXCEEDED:" + name)
        attempts[name] += 1
        try:
            raw = source(*args)
        except HICPContextError as exc:
            # The official HICP adapter wraps transport failures, but its
            # structural validation errors must continue to fail closed.
            if name == "eurostat_hicp" and isinstance(exc.__cause__, OSError):
                raise URLError("OFFICIAL_EUROSTAT_HICP_NETWORK_UNAVAILABLE") from exc
            raise
        if name == "eurostat_hicp":
            # The established HICP official adapter already parses JSON-stat.
            # Never misinterpret its typed response as original HTTP bytes.
            try:
                size = len(json.dumps(raw, allow_nan=False).encode("utf-8"))
            except (TypeError, ValueError, RecursionError, OverflowError) as exc:
                raise OneShotBlocked("HICP_JSONSTAT_INVALID") from exc
            if type(raw) is not dict or not 0 < size <= MAX_SOURCE_BYTES:
                raise OneShotBlocked("HICP_JSONSTAT_INVALID")
        else:
            raw = _bytes(raw)
        counts[name] += 1
        return raw

    # Same UKNF original HTTP bytes feed both the original-evidence validator
    # and the v0.7 NAV statistics; no hidden second GET or inferred history.
    knf_raw: list[bytes] = []

    def captured_knf(url: str) -> bytes:
        raw = read("uknf", knf_fetch, url)
        knf_raw.append(raw)
        return raw

    nav_original = observe_knf(fetch=captured_knf, clock=stamp)
    if len(knf_raw) not in (3, 4):
        raise OneShotBlocked("UKNF_ORIGINAL_SOURCE_SET_INCOMPLETE")
    nav_quality = describe_unit_nav(
        knf_raw[0], knf_raw[1], knf_raw[2],
        knf_raw[3] if len(knf_raw) == 4 else None, observed_at=stamp(),
    )

    original_mf = read("mf", mf_fetch, MF_URL)
    mf_clock = stamp()
    mf_schema = inspect_market_sheet(original_mf, observed_at=mf_clock)
    mf_turnover = analyze_mf_original(original_mf, completed_at=mf_clock)
    if (mf_schema.get("sha256") != mf_turnover.get("source_sha256")
            or nav_quality.get("source_history_sha256") !=
            nav_original.get("source_documents", {}).get("history_sha256")):
        raise OneShotBlocked("ORIGINAL_SOURCE_FINGERPRINT_MISMATCH")

    macro_unavailable = False
    separate_eurostat = {}
    independent_nbp_fx_archive = None
    try:
        macro = observe_macro(
            nbp_fetch=lambda url: read("nbp", nbp_fetch, url),
            hicp_fetch=lambda url: read("eurostat_hicp", hicp_fetch, url),
            yield_fetch=lambda: read("eurostat_yield", yield_fetch),
            clock=stamp,
            nbp_chunk_days=10,
        )
    except (HTTPError, URLError):
        if not allow_macro_unavailable:
            raise
        # A failed public HTTP request is an unavailable source, never a zero
        # observation or a reason to synthesize NBP/Eurostat levels.
        macro = None
        macro_unavailable = True
        if nbp_archive_fetch is not None:
            try:
                independent_nbp_fx_archive = inspect_nbp_fx_archive(
                    read("nbp_archive_fx", nbp_archive_fetch,
                         NBP_FX_ARCHIVE_URL), observed_at=stamp())
            except (HTTPError, URLError):
                pass
        # Independent Eurostat originals remain worth validating after an
        # NBP HTTP failure. Never retry a request that was already attempted.
        if attempts["eurostat_hicp"] == 0:
            try:
                hicp = inspect_hicp(
                    read("eurostat_hicp", hicp_fetch,
                         hicp_query(HICP_SINCE, HICP_UNTIL)),
                    since=HICP_SINCE, until=HICP_UNTIL,
                    retrieval_scope="EUROSTAT_PUBLIC_READ_ONLY")
                if (hicp["status"] != "AVAILABLE_CONTEXT_NOT_HISTORICAL_PIT"
                        or hicp["observed_month_count"] != 13):
                    raise OneShotBlocked("INCOMPLETE_EUROSTAT_HICP")
                separate_eurostat["hicp"] = hicp
            except (HTTPError, URLError):
                pass
        if attempts["eurostat_yield"] == 0:
            try:
                yield_raw = read("eurostat_yield", yield_fetch)
                yields = parse_original_yields(yield_raw, observed_at=stamp())
                if yields["observed_months"] != 59:
                    raise OneShotBlocked("INCOMPLETE_EUROSTAT_YIELD")
                separate_eurostat["yield"] = (yields, yield_raw)
            except (HTTPError, URLError):
                pass
    if not macro_unavailable and (
            counts["mf"] != 1 or counts["nbp"] != 6
            or counts["eurostat_hicp"] != 1 or counts["eurostat_yield"] != 1):
        raise OneShotBlocked("PUBLIC_SOURCE_SET_INCOMPLETE")
    completed = stamp()
    sources = {
        "nav_quality": nav_quality,
        "mf_schema": mf_schema,
        "observed_at": completed,
    }
    if not macro_unavailable:
        sources.update(macro_reference=macro, mf_turnover=mf_turnover,
                       nav_original=nav_original)
    report = compose_market_research(**sources)
    if (report["mode"] != ("SCHEMA_ONLY" if macro_unavailable
                           else "DESCRIPTIVE_MARKET_CONTEXT")
            or report["m1_m2_m3"] != "INSUFFICIENT_DATA_HOLD_CASH"
            or report["asset_total_return_qualified"] != []
            or any(report[key] != 0 for key in
                   ("financial_operations", "orders_sent", "database_writes"))):
        raise OneShotBlocked("UNSAFE_RESEARCH_PROMOTION")
    standalone = None
    if macro_unavailable:
        standalone = {
            "scope": "INDEPENDENT_ORIGINAL_REFERENCES_NOT_CROSS_MARKET_COMPARISON",
            "mf_source_sha256": mf_schema["sha256"],
            "mf_months": mf_turnover["unique_month_count"],
            "mf_latest_total_mln_pln": mf_turnover["latest_total_mln_pln"],
            "uknf_source_sha256": nav_quality["source_history_sha256"],
            "uknf_same_class_nav_days": nav_quality["distinct_valuation_days"],
            "uknf_level_change_not_total_return_pct": nav_quality.get(
                "first_to_last_nav_level_change_pct_not_total_return"),
        }
        if independent_nbp_fx_archive is not None:
            ref = independent_nbp_fx_archive
            standalone.update(
                nbp_fx_archive_url=ref["source_url"],
                nbp_fx_archive_original_sha256=ref["original_csv_sha256"],
                nbp_fx_archive_september_days=ref["september_2026_days"],
                nbp_fx_archive_latest_usdpln_mid=ref["latest_usdpln_mid"],
                nbp_fx_archive_latest_eurpln_mid=ref["latest_eurpln_mid"])
        if "hicp" in separate_eurostat:
            hicp = separate_eurostat["hicp"]
            standalone.update(
                eurostat_hicp_months=hicp["observed_month_count"],
                eurostat_hicp_canonical_sha256=hicp["source_payload_canonical_sha256"])
        if "yield" in separate_eurostat:
            yields, _ = separate_eurostat["yield"]
            standalone.update(
                eurostat_yield_months=yields["observed_months"],
                eurostat_yield_original_sha256=yields["original_response_sha256"])
        if len(separate_eurostat) == 2:
            hicp = separate_eurostat["hicp"]
            _, yield_raw = separate_eurostat["yield"]
            with localcontext() as context:
                context.prec = 40
                observations = hicp["observations"]
                inflation = (Decimal(observations[-1]["index_2025_100"]) /
                             Decimal(observations[0]["index_2025_100"]) - 1) * 100
                nominal = _sep2026_bond_yield(yield_raw)
                standalone.update(
                    eurostat_pl_nominal_10y_yield_pct=str(nominal),
                    eurostat_trailing_12m_hicp_pct=f"{inflation:.4f}",
                    eurostat_level_gap_pp_not_real_yield=f"{nominal-inflation:.4f}")
    return {
        "schema": SCHEMA,
        "status": ("PARTIAL_MACRO_HTTP_UNAVAILABLE" if macro_unavailable else
                   "ALL_PUBLIC_SOURCE_RECEIPTS_VALIDATED_DESCRIPTIVE_ONLY"),
        "started_at_utc": started.isoformat(),
        "completed_at_utc": completed.isoformat(),
        "source_read_counts": counts,
        "source_read_attempts": attempts,
        "total_public_reads": sum(counts.values()),
        "macro_source_status": (
            "HTTP_UNAVAILABLE_NO_VALUES_FABRICATED" if macro_unavailable
            else "VALIDATED"),
        "independent_descriptive_context": standalone,
        "original_market_bytes_saved": 0,
        "historical_pit_certified": False,
        "financial_operations": 0,
        "orders_sent": 0,
        "database_writes": 0,
        "report": report,
    }


def main(argv: list[str] | None = None, *, runner: Callable = run_once) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-public-official-read", action="store_true",
                        help="Opt in to the fixed official HTTPS source requests")
    parser.add_argument("--allow-macro-unavailable", action="store_true",
                        help="Emit explicit PARTIAL MF/UKNF research if macro HTTP fails")
    parser.add_argument("--out-dir", required=True,
                        help="New local DEV report directory; existing paths are refused")
    args = parser.parse_args(argv)
    if not args.allow_public_official_read:
        parser.error("EXPLICIT_PUBLIC_SOURCE_READ_OPT_IN_REQUIRED")
    target = Path(args.out_dir)
    if target.exists() or target.is_symlink():
        parser.error("OUT_DIR_MUST_NOT_EXIST")
    # Complete all network reads and cross-source validation in RAM before
    # creating any output directory, so incomplete sources leave no reports.
    result = runner(
        knf_fetch=official_source_fetch, mf_fetch=fetch_exact,
        nbp_fetch=official_nbp_fetch, hicp_fetch=official_hicp_fetch,
        yield_fetch=official_yield_fetch,
        nbp_archive_fetch=official_nbp_fx_archive_fetch,
        allow_macro_unavailable=args.allow_macro_unavailable,
    )
    report = result["report"]
    receipt = {key: value for key, value in result.items() if key != "report"}
    receipt["market_report_sha256"] = report["receipt_sha256"]
    target.mkdir(parents=True, mode=0o700, exist_ok=False)
    with (target / "market_research_v07.json").open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
    with (target / "market_research_v07.md").open("x", encoding="utf-8") as handle:
        handle.write(render_markdown(report))
        if result["independent_descriptive_context"] is not None:
            separate = result["independent_descriptive_context"]
            handle.write("\n## Częściowy odczyt źródeł — bez agregacji\n\n")
            handle.write("- Pełny zestaw NBP/Eurostat: niedostępny przez HTTP; "
                         "nie uzupełniono braków szacunkami.\n")
            handle.write(f"- MF: {separate['mf_months']} miesięcy, "
                         f"ostatni obrót {separate['mf_latest_total_mln_pln']} mln PLN "
                         "(to nie stopa zwrotu).\n")
            handle.write(f"- UKNF: {separate['uknf_same_class_nav_days']} dni NAV "
                         "(nie całkowity zwrot inwestora).\n")
            if "nbp_fx_archive_september_days" in separate:
                handle.write(
                    f"- NBP archiwum A: {separate['nbp_fx_archive_september_days']} "
                    "dni kursów USD/EUR, tylko ceny referencyjne; "
                    "seria NBP złota nadal niekompletna.\n")
            if "eurostat_hicp_months" in separate:
                handle.write(f"- Eurostat HICP: {separate['eurostat_hicp_months']} "
                             "zweryfikowanych miesięcy indeksu cen.\n")
            if "eurostat_yield_months" in separate:
                handle.write(f"- Eurostat PL 10Y: {separate['eurostat_yield_months']} "
                             "zweryfikowanych miesięcy nominalnej rentowności.\n")
            if "eurostat_level_gap_pp_not_real_yield" in separate:
                handle.write("- Nominalna rentowność minus roczna zmiana HICP: "
                             f"{separate['eurostat_level_gap_pp_not_real_yield']} p.p. "
                             "(tylko różnica poziomów, nie realny zwrot).\n")
    with (target / "public_source_run_v08.json").open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
    print("ISL_PUBLIC_ONE_SHOT_V08=" + json.dumps({
        "status": ("PARTIAL" if result["independent_descriptive_context"] is not None
                   else "PASS"),
        "source_reads": result["total_public_reads"],
        "market_report_sha256": report["receipt_sha256"],
        "m1_m2_m3": report["m1_m2_m3"], "financial_operations": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
