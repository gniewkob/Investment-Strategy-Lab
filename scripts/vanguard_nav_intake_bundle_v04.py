"""Prepare a local, non-trading Vanguard NAV+NBP research intake bundle.

Input is an original, voluntarily obtained XLSX and official public NBP
archive. No legal confirmations are performed. The original XLSX is
never uploaded to a server, copied into the repo, or written to Neon.

Offline by default. With --fetch-exact-nbp, ONLY missing same-calendar-day
official USD/PLN table-A quotes are requested from api.nbp.pl.
No nearest-neighbor FX, interpolation, portfolio fills, financial trades,
historical PIT certification or investable-return claims.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.reference_archive_calendar_v04 import _digest, _verify_digest
from scripts.vanguard_xlsx_offline_intake_v04 import inspect_export

MAX_FX_BYTES = 350_000
NBP_BASE = "https://api.nbp.pl/api"
CODE = "USDPLN_NBP"
ORIGINAL_FUND_ISIN = "IE00BK5BQT80"


def _positive(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("quote must be a positive decimal")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid decimal") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError("quote must be finite and positive")
    return number


def _timestamp(clock):
    now = clock()
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError("UTC timezone-aware clock required")
    return now.astimezone(timezone.utc).isoformat()


def _official_fx_source(url):
    u = urlsplit(url)
    if (u.scheme != "https" or u.hostname != "api.nbp.pl"
            or u.username or u.password or u.fragment
            or not u.path.startswith("/api/exchangerates/tables/a/")):
        raise ValueError("unapproved official USDPLN source URL")


def _fetch_public_fx(url):
    _official_fx_source(url)
    request = Request(url, headers={"Accept": "application/json",
                                     "User-Agent": "ISL-NAV-research/0.4"})
    with urlopen(request, timeout=18) as response:
        if response.status != 200:
            raise ValueError("official NBP did not return HTTP 200")
        data = response.read(MAX_FX_BYTES + 1)
        if len(data) > MAX_FX_BYTES:
            raise ValueError("NBP response exceeds research limit")
        return data


def _parse_fx(day, url, raw, retrieved_at):
    _official_fx_source(url)
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_FX_BYTES:
        raise ValueError("bounded official NBP JSON bytes required")
    try:
        response = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid NBP JSON") from exc
    if not isinstance(response, list) or len(response) != 1:
        raise ValueError("no exact-day official NBP table A release")
    entry = response[0]
    if (not isinstance(entry, dict) or entry.get("table") != "A"
            or entry.get("effectiveDate") != day
            or not isinstance(entry.get("rates"), list)):
        raise ValueError("NBP observed_for differs from requested date")
    matches = [r for r in entry["rates"]
               if isinstance(r, dict) and r.get("code") == "USD"]
    if len(matches) != 1:
        raise ValueError("exactly one official USD reference rate required")
    value = _positive(str(matches[0]["mid"]))
    return {"observed_for": day,
            "usdpln": str(value),
            "source": "NBP_TABLE_A_MID_FX_RATE",
            "source_url": url,
            "raw_response_sha256": sha256(raw).hexdigest(),
            "retrieved_at": retrieved_at,
            "historical_first_available_at": None}


def _verified_original_fx(archive):
    _verify_digest(archive)
    if (archive.get("source") != "NBP_OFFICIAL_API"
            or archive.get("data_kind") != "NON_EXECUTABLE_REFERENCE_ONLY"
            or archive.get("historical_vintage_verified") is not False
            or archive.get("series_contract", {}).get("usdpln", {}).get("return_basis") != "FX_RATE"):
        raise ValueError("not a verified-contract NBP public archive")
    windows = archive.get("source_windows")
    rows = archive.get("monthly_observations", {}).get("usdpln")
    if not isinstance(windows, list) or not windows or not isinstance(rows, list):
        raise ValueError("missing original public NBP source receipts")
    receipts = []
    for window in windows:
        lo, hi = date.fromisoformat(window["from"]), date.fromisoformat(window["to"])
        rec = window["receipts"]["fx"]
        _official_fx_source(rec["url"])
        if lo > hi or (hi-lo).days >= 93:
            raise ValueError("invalid window range")
        receipts.append((lo, hi, rec))
    indexed = {}
    for row in rows:
        day = date.fromisoformat(row["observed_for"])
        month = row["month"]
        if month in indexed or month != day.strftime("%Y-%m"):
            raise ValueError("duplicate or misdated NBP month")
        candidates = [
            rec for lo, hi, rec in receipts
            if lo <= day <= hi
            and rec.get("url") == row.get("source_url")
            and rec.get("sha256") == row.get("raw_sha256")
            and rec.get("retrieved_at") == row.get("retrieved_at")
        ]
        if len(candidates) != 1:
            raise ValueError("NBP monthly reference not linked to source receipt")
        indexed[month] = {"observed_for": day.isoformat(),
                          "usdpln": str(_positive(str(row["value"]))),
                          "source": "NBP_TABLE_A_MID_FX_RATE",
                          "source_url": row["source_url"],
                          "raw_response_sha256": row["raw_sha256"],
                          "retrieved_at": row["retrieved_at"],
                          "historical_first_available_at": None}
    return indexed


def prepare(raw_xlsx: bytes, nbp_archive: dict, first_month: str,
            last_month: str, *, fetch=None,
            clock=lambda: datetime.now(timezone.utc)) -> dict:
    now = clock()
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError("UTC clock required")
    intake = inspect_export(raw_xlsx, first_month, last_month, as_of=now.date())
    fx_months = _verified_original_fx(nbp_archive)
    if intake["months"] > 72 or intake["months"] < 36:
        raise ValueError("unsupported NAV horizon")
    mismatches = []
    values = {}
    for row in intake["monthly"]:
        month, navday = row["month"], row["observed_for"]
        original = fx_months.get(month)
        if original is None:
            raise ValueError("official NBP source is missing calendar month " + month)
        if original["observed_for"] == navday:
            values[month] = original
        else:
            mismatches.append({"month": month, "nav_date": navday,
                                "original_nbp_date": original["observed_for"]})
    if fetch is not None:
        # Each missing date costs one public read, not a whole month of data.
        by_date = {}
        for item in mismatches:
            day = item["nav_date"]
            if day not in by_date:
                url = f"{NBP_BASE}/exchangerates/tables/a/{day}/{day}/?format=json"
                raw = fetch(url)
                by_date[day] = _parse_fx(day, url, raw, _timestamp(clock))
            values[item["month"]] = by_date[day]
    eligible = len(values) == intake["months"]
    converted = []
    if eligible:
        for row in intake["monthly"]:
            month = row["month"]
            matched = values[month]
            if matched["observed_for"] != row["observed_for"]:
                raise AssertionError("date mismatch leaked into valuation")
            value = Decimal(row["nav_usd"]) * Decimal(matched["usdpln"])
            converted.append({
                "month": month,
                "observed_for": row["observed_for"],
                "nav_usd": row["nav_usd"],
                "usdpln_nbp": matched["usdpln"],
                "nav_pln_reference": format(value, "f"),
                "nbp_source_url": matched["source_url"],
                "nbp_response_sha256": matched["raw_response_sha256"],
                "nbp_retrieved_at": matched["retrieved_at"],
            })
    output = {
        "status": ("CANDIDATE_NAV_PLN_REFERENCE_READY_FOR_SOURCE_REVIEW"
                   if eligible else "BLOCKED_NEEDS_EXACT_DAY_NBP_FX"),
        "nav_candidate_file_sha256": intake["raw_export_sha256"],
        "nav_candidate_sha256": intake["candidate_sha256"],
        "nbp_source_document_sha256": nbp_archive["evidence_sha256"],
        "months_requested": intake["months"],
        "first_month": intake["first_month"],
        "last_month": intake["last_month"],
        "missing_exact_day_fx": [] if eligible else mismatches,
        "official_extra_fx_reads": (len({x["nav_date"] for x in mismatches})
                                    if fetch is not None else 0),
        "monthly": converted,
        "instrument_code": "VANGUARD_ACC_NAV_REFERENCE_PLN",
        "fund_isin_from_document": None,
        "expected_isin_to_verify_externally": ORIGINAL_FUND_ISIN,
        "fund_identity_authenticated_from_original_file": False,
        "raw_xlsx_layout_validated_against_actual_provider_file": False,
        "original_publication_time_certified": False,
        "historical_pit_certified": False,
        "executable_market_fill_price": False,
        "usable_as_GLOBAL_EQUITY_TR_PLN": False,
        "real_model_backtest": "NOT_RUN_PENDING_ORIGINAL_NAV_PROVENANCE",
        "real_orders": 0,
        "paper_events_created": 0,
        "database_writes": 0,
        "financial_operations": 0,
    }
    output["evidence_sha256"] = _digest(output)
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--xlsx", type=Path, required=True,
                   help="original local NAV workbook; NEVER committed to GitHub")
    p.add_argument("--nbp-archive", type=Path, required=True)
    p.add_argument("--first-month", default="2021-11")
    p.add_argument("--last-month", default="2026-10")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--fetch-exact-nbp", action="store_true",
                   help="allow only api.nbp.pl reads for missing exact NAV dates")
    args = p.parse_args()
    if args.out.resolve() == args.xlsx.resolve():
        p.error("--out must not overwrite the original source XLSX")
    result = prepare(
        args.xlsx.read_bytes(),
        json.loads(args.nbp_archive.read_text(encoding="utf-8")),
        args.first_month, args.last_month,
        fetch=_fetch_public_fx if args.fetch_exact_nbp else None,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True)
                        + "\n", encoding="utf-8")
    print("ISL_NAV_INTAKE=" + json.dumps({
        k: result[k] for k in (
            "status", "months_requested", "official_extra_fx_reads",
            "nav_candidate_file_sha256", "evidence_sha256",
            "real_model_backtest", "financial_operations",
        )
    }, sort_keys=True))
    # Status remains explicitly blocked until independent source review.


if __name__ == "__main__":
    main()
