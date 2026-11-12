"""Public-first historical NBP reference laboratory: research, never investment.

Uses only public NBP HTTPS Table A USD/EUR mid FX and NBP gold price PLN/g.
Old monthly prices are today's archive snapshot, NOT historical data vintages.
Fixed 100 PLN/month contributions buy NON-EXECUTABLE reference units only.
This module never opens accounts, sends orders or writes to databases.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import json
import re
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from scripts.nbp_reference_capture import capture

D = Decimal
SOURCE_SERIES = ("gold", "usdpln", "eurpln")
LEVEL_CONCEPTS = {
    "gold": "NBP_PRICE_ONLY_PLN_PER_GRAM_NOT_TOTAL_RETURN",
    "usdpln": "NBP_TABLE_A_MID_PLN_PER_USD_NOT_EXECUTABLE_FX",
    "eurpln": "NBP_TABLE_A_MID_PLN_PER_EUR_NOT_EXECUTABLE_FX",
}
MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
MAX_MONTHS = 60
MAX_HTTP_BYTES = 500_000
MAX_CHUNK_DAYS = 90
CONTRIBUTION = D("100")
STRESS_COST_BPS = D("30")


class PublicReferenceBlocked(ValueError):
    """Bad input, incomplete public history or source-integrity issue."""


def _month(value: str) -> tuple[int, int]:
    if not isinstance(value, str) or not MONTH_RE.fullmatch(value):
        raise PublicReferenceBlocked("INVALID_MONTH")
    year, month = map(int, value.split("-"))
    if not (2013 <= year <= 2100 and 1 <= month <= 12):
        raise PublicReferenceBlocked("INVALID_MONTH")
    return year, month


def _next(month: tuple[int, int]) -> tuple[int, int]:
    year, m = month
    return (year + 1, 1) if m == 12 else (year, m + 1)


def _months(start: str, end: str, today: date) -> list[str]:
    a, b = _month(start), _month(end)
    if a > b or b >= (today.year, today.month):
        raise PublicReferenceBlocked("ONLY_COMPLETED_HISTORICAL_MONTHS")
    out = []
    while a <= b:
        out.append(f"{a[0]:04d}-{a[1]:02d}")
        if len(out) > MAX_MONTHS:
            raise PublicReferenceBlocked("WINDOW_EXCEEDS_60_MONTHS")
        a = _next(a)
    if len(out) < 12:
        raise PublicReferenceBlocked("REQUIRES_AT_LEAST_12_MONTHS")
    return out


def _ranges(first: date, last: date):
    cursor = first
    while cursor <= last:
        stop = min(last, cursor + timedelta(days=MAX_CHUNK_DAYS - 1))
        yield cursor.isoformat(), stop.isoformat()
        cursor = stop + timedelta(days=1)


class _NoRedirect(HTTPRedirectHandler):
    """Refuse HTTP redirects before urllib can contact their target host."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise PublicReferenceBlocked("UNEXPECTED_NBP_REDIRECT_OR_STATUS")


def official_fetch(url: str) -> bytes:
    """Strict NBP HTTPS origin, no redirects, bounded payload; no credentials."""
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc != "api.nbp.pl"
            or not parsed.path.startswith("/api/") or
            parsed.query != "format=json" or parsed.fragment):
        raise PublicReferenceBlocked("NON_OFFICIAL_NBP_ENDPOINT")
    req = Request(url, headers={"Accept": "application/json",
                                "User-Agent": "ISL-public-first-educational/1"})
    # A response.geturl() check alone is too late: urlopen follows 30x first.
    # Use a request-local opener; never alter process-global urllib behavior.
    opener = build_opener(_NoRedirect(), HTTPSHandler())
    with opener.open(req, timeout=25) as response:
        final = urlsplit(response.geturl())
        if (response.status != 200 or final.scheme != "https"
                or final.netloc != parsed.netloc or
                final.path != parsed.path or final.query != parsed.query):
            raise PublicReferenceBlocked("UNEXPECTED_NBP_REDIRECT_OR_STATUS")
        raw = response.read(MAX_HTTP_BYTES + 1)
    if not raw or len(raw) > MAX_HTTP_BYTES:
        raise PublicReferenceBlocked("NBP_PAYLOAD_OUT_OF_BOUNDS")
    return raw


def _level(value: object) -> Decimal:
    if not isinstance(value, str) or value.strip() != value:
        raise PublicReferenceBlocked("NON_CANONICAL_PUBLIC_REFERENCE_VALUE")
    try:
        number = D(value)
    except (ValueError, InvalidOperation) as exc:
        raise PublicReferenceBlocked("INVALID_PUBLIC_REFERENCE_VALUE") from exc
    if not number.is_finite() or number <= 0:
        raise PublicReferenceBlocked("INVALID_PUBLIC_REFERENCE_VALUE")
    return number


def _money(value: Decimal) -> str:
    return format(value.quantize(D(".01")), "f")


def _scenarios(months: list[str], levels: dict[str, list[dict]]) -> list[dict]:
    contributed = CONTRIBUTION * len(months)
    scenarios = [{
        "code": "CASH_PLN_ZERO_INTEREST_REFERENCE",
        "source_kind": "NOMINAL_CASH_COMPARISON_NOT_BANK_ACCOUNT",
        "assumed_one_way_cost_bps": "0",
        "virtual_contributions_pln": _money(contributed),
        "terminal_reference_value_pln": _money(contributed),
        "difference_vs_nominal_cash_pln": "0.00",
        "executable_asset": False,
    }]
    with localcontext() as ctx:
        ctx.prec = 45
        for asset in SOURCE_SERIES:
            values = [_level(row["value"]) for row in levels[asset]]
            for cost in (D("0"), STRESS_COST_BPS):
                units = sum(
                    (CONTRIBUTION / (D("1") + cost / D("10000"))) / value
                    for value in values
                )
                terminal = units * values[-1]
                scenarios.append({
                    "code": asset.upper() + "_NON_EXECUTABLE_MONTH_END_REFERENCE",
                    "source_kind": LEVEL_CONCEPTS[asset],
                    "assumed_one_way_cost_bps": str(cost),
                    "virtual_contributions_pln": _money(contributed),
                    "terminal_reference_value_pln": _money(terminal),
                    "difference_vs_nominal_cash_pln": _money(terminal - contributed),
                    "executable_asset": False,
                })
    return scenarios


def research_public_nbp(start_month: str = "2021-11",
                        end_month: str = "2026-10", *,
                        fetch=None, clock=None, today: date | None = None) -> dict:
    """One-shot complete historic 60-month snapshot, with explicit public fetch.

    One retrospective calculation is NOT a genuine historic decision replay.
    No NBP publication *hour*, daily revision vintage or executable trade price
    is reconstructed. Scenario values are index-reference arithmetic.
    """
    if fetch is None:
        raise PublicReferenceBlocked("EXPLICIT_PUBLIC_NBP_FETCH_OPT_IN_REQUIRED")
    today = today or datetime.now(timezone.utc).date()
    months = _months(start_month, end_month, today)
    first = date.fromisoformat(months[0] + "-01")
    next_after_last = _next(_month(months[-1]))
    last = date(*next_after_last, 1) - timedelta(days=1)

    by_date = {asset: {} for asset in SOURCE_SERIES}
    raw_receipts = []
    for begin, finish in _ranges(first, last):
        options = {"fetch": fetch}
        if clock is not None:
            options["clock"] = clock
        try:
            part = capture(begin, finish, **options)
        except (ValueError, TypeError, KeyError, OSError) as exc:
            raise PublicReferenceBlocked("NBP_CHUNK_REJECTED") from exc
        if (part.get("source") != "NBP" or
                part.get("gold_basis") != "PRICE_ONLY_PLN_PER_GRAM" or
                part.get("fx_basis") != "TABLE_A_MID_PLN_PER_FOREIGN_UNIT" or
                part.get("pit_status") !=
                "UNVERIFIED_HISTORICAL_VINTAGE_AND_PUBLICATION_TIME"):
            raise PublicReferenceBlocked("NBP_SOURCE_SEMANTICS_CHANGED")
        receipts = part.get("receipts")
        if not isinstance(receipts, dict) or set(receipts) != {"fx", "gold"}:
            raise PublicReferenceBlocked("NBP_SOURCE_RECEIPT_MISSING")
        for kind in ("fx", "gold"):
            rec = receipts[kind]
            expected_path = ("/api/exchangerates/tables/a/" if kind == "fx"
                             else "/api/cenyzlota/")
            if (not isinstance(rec, dict) or
                    rec.get("url") !=
                    f"https://api.nbp.pl{expected_path}{begin}/{finish}/?format=json"
                    or not re.fullmatch(r"[0-9a-f]{64}", rec.get("sha256", ""))):
                raise PublicReferenceBlocked("NBP_RECEIPT_WRONG_SOURCE")
            raw_receipts.append({
                "kind": kind, "start": begin, "end": finish,
                "url": rec["url"], "sha256": rec["sha256"],
                "retrieved_at": rec["retrieved_at"],
            })
        for asset in SOURCE_SERIES:
            rows = part.get("series", {}).get(asset)
            if not isinstance(rows, list) or not rows:
                raise PublicReferenceBlocked("EMPTY_NBP_CHUNK_SERIES")
            for row in rows:
                if (row.get("basis") !=
                    ("PRICE_ONLY_PLN_PER_GRAM" if asset == "gold"
                     else "TABLE_A_MID_PLN_PER_FOREIGN_UNIT") or
                        row.get("currency") != "PLN" or
                        row.get("historical_vintage_verified") is not False or
                        row.get("available_at") is not None):
                    raise PublicReferenceBlocked("NBP_REFERENCE_TYPE_CONFLICT")
                day = date.fromisoformat(row["publication_date"])
                if not (date.fromisoformat(begin) <= day <= date.fromisoformat(finish)
                        and row.get("observed_for") == row.get("publication_date")):
                    raise PublicReferenceBlocked("NBP_DATE_OUTSIDE_CHUNK")
                if day in by_date[asset]:
                    raise PublicReferenceBlocked("DUPLICATE_PUBLICATION_DATE")
                _level(row.get("value"))
                by_date[asset][day] = row

    monthly = {asset: [] for asset in SOURCE_SERIES}
    for ym in months:
        year, month = _month(ym)
        for asset in SOURCE_SERIES:
            dates = sorted(d for d in by_date[asset] if (d.year, d.month) == (year, month))
            if not dates or dates[-1].day < 20:
                raise PublicReferenceBlocked("MISSING_LATE_MONTH_NBP_PUBLICATION")
            row = by_date[asset][dates[-1]]
            monthly[asset].append({
                "month": ym,
                "publication_date": dates[-1].isoformat(),
                "value": row["value"],
            })
    # The digest is an exact *derived value-set* digest, not historic PIT proof.
    canonical = json.dumps(monthly, separators=(",", ":"), sort_keys=True)
    digest = sha256(canonical.encode("utf-8")).hexdigest()
    for asset in SOURCE_SERIES:
        if len(monthly[asset]) != len(months):
            raise PublicReferenceBlocked("MONTH_ALIGNMENT_INVALID")
    return {
        "schema": "ISL_PUBLIC_FIRST_NBP_REFERENCE_RESEARCH_V01",
        "status": "PUBLIC_REFERENCE_RESEARCH_ONLY",
        "first_month": months[0], "last_month": months[-1],
        "complete_months": len(months), "monthly_contribution_pln": "100.00",
        "raw_source_receipts": raw_receipts,
        "daily_counts": {asset: len(by_date[asset]) for asset in SOURCE_SERIES},
        "monthly_selected_dates": {
            asset: [row["publication_date"] for row in monthly[asset]]
            for asset in SOURCE_SERIES
        },
        "monthly_values_canonical_sha256": digest,
        "actual_nbp_reference_values_used": True,
        "historical_source_vintage_certified": False,
        "historical_publication_hour_certified": False,
        "source_api_is_public": True,
        "model_qualifications_granted": [],
        "legacy_m1_m2_m3": "NOT_RUN_UNQUALIFIED_TOTAL_RETURN_SERIES",
        "scenarios": _scenarios(months, monthly),
        "account_connections": 0, "paper_events_created": 0,
        "database_connections": 0, "database_writes": 0,
        "financial_operations": 0,
        "investment_performance_or_prediction_proven": False,
        "footnote": (
            "Historical reference-value arithmetic, NOT historical PIT, "
            "tradable fills or expected performance. All strategies spend "
            "the same hypothetical 100 PLN/month at late-month reference "
            "levels; 30 bps is an assumed cost stress, not a provider quote."
        ),
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-month", default="2021-11")
    parser.add_argument("--end-month", default="2026-10")
    parser.add_argument("--allow-public-nbp-fetch", action="store_true")
    args = parser.parse_args()
    if not args.allow_public_nbp_fetch:
        parser.error("public NBP fetch requires --allow-public-nbp-fetch")
    receipt = research_public_nbp(
        args.start_month, args.end_month, fetch=official_fetch)
    # Fixed envelope only: no raw market-history files or complete prices in CI.
    safe = {k: v for k, v in receipt.items() if k != "monthly_selected_dates"}
    print("PUBLIC_FIRST_NBP_RESEARCH_RECEIPT=" +
          json.dumps(safe, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
