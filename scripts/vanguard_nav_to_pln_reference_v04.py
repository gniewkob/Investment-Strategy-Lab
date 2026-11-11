"""Strict OFFLINE Vanguard accumulating NAV USD -> official NBP USD/PLN.

Research-only valuation reference, NOT a tradable fill price or an
equity total-return benchmark. Uses only exact same-date published
NBP rate; blocks month/date gaps rather than forward filling.
Requires original NAV download bytes to verify source SHA-256.
No network, database, order, paper event or financial account calls.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from urllib.parse import urlsplit
import json
import re
import csv
import io

from scripts.reference_archive_calendar_v04 import _verify_digest, _digest

ISIN = "IE00BK5BQT80"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _positive(x, label):
    if isinstance(x, bool) or not isinstance(x, (str, int, Decimal)):
        raise ValueError(label + " is not decimal")
    try:
        v = Decimal(str(x))
    except (ValueError, InvalidOperation) as e:
        raise ValueError(label + " is not decimal") from e
    if not v.is_finite() or v <= 0:
        raise ValueError(label + " must be finite positive")
    return v


def _official(url):
    if not isinstance(url, str):
        raise ValueError("Vanguard source URL required")
    u = urlsplit(url)
    host = (u.hostname or "").lower()
    allowed = (host == "www.vanguard.co.uk"
               or host == "vanguard.co.uk"
               or host == "www.pl.vanguard"
               or host == "www.ch.vanguard"
               or host.endswith(".vanguard.com"))
    if (u.scheme != "https" or not allowed or u.username
            or u.password or u.fragment):
        raise ValueError("official Vanguard HTTPS provenance required")


def _parse_utc(value):
    if not isinstance(value, str):
        raise ValueError("UTC retrieved_at timestamp required")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError("UTC retrieved_at timestamp required") from e
    if timestamp.tzinfo is None or timestamp.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError("explicit UTC retrieval timestamp required")
    return timestamp


def _month_start(month):
    if not isinstance(month, str) or not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ValueError("YYYY-MM month expected")
    try:
        return date.fromisoformat(month + "-01")
    except ValueError as e:
        raise ValueError("invalid monthly date") from e


def _next_month(d):
    return date(d.year + (d.month == 12), (d.month % 12) + 1, 1)


def match_official_nav_to_fx(nav_document: dict, original_download_bytes: bytes,
                             nbp_document: dict) -> dict:
    if not isinstance(nav_document, dict) or not isinstance(nbp_document, dict):
        raise ValueError("expected two source manifests")
    if not isinstance(original_download_bytes, bytes) or not original_download_bytes:
        raise ValueError("original Vanguard export bytes required")
    if (nav_document.get("source") != "VANGUARD_OFFICIAL_NAV_USD_ACC"
            or nav_document.get("isin") != ISIN
            or nav_document.get("quote_currency") != "USD"
            or nav_document.get("basis") != "ACCUMULATING_FUND_NAV_USD"
            or nav_document.get("instrument_kind") != "NON_EXECUTABLE_NAV_REFERENCE"
            or nav_document.get("historical_vintage_verified") is not False
            or nav_document.get("historical_first_publication_verified") is not False):
        raise ValueError("unverified NAV source basis, identity or vintage")
    _official(nav_document.get("source_url"))
    _parse_utc(nav_document.get("retrieved_at"))
    digest = sha256(original_download_bytes).hexdigest()
    if not isinstance(nav_document.get("raw_export_sha256"), str) \
       or not HEX64.fullmatch(nav_document["raw_export_sha256"]) \
       or digest != nav_document["raw_export_sha256"]:
        raise ValueError("Vanguard original source bytes SHA-256 mismatch")
    monthly = nav_document.get("monthly")
    if not isinstance(monthly, list) or not 36 <= len(monthly) <= 72:
        raise ValueError("36-72 monthly verified NAV observations required")
    # The monthly values are NOT trusted just because they appear beside
    # the raw-file hash. Independently reproduce each value from the actual
    # source bytes. Supported CSV format is a deliberately narrow candidate;
    # official Vanguard Excel bytes require separate format validation.
    if nav_document.get("raw_file_format") != "CSV_DATE_NAV_USD_V1":
        raise ValueError("Vanguard XLSX/raw format not independently parsed")
    try:
        raw_text = original_download_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise ValueError("NAV file is not UTF-8 CSV") from e
    reader = csv.DictReader(io.StringIO(raw_text, newline=""))
    if reader.fieldnames != ["date", "nav_usd"]:
        raise ValueError("NAV CSV header must be date,nav_usd")
    parsed = {}
    seen_dates = set()
    for idx, row in enumerate(reader):
        if idx >= 6000 or set(row) != {"date", "nav_usd"}:
            raise ValueError("unbounded or ambiguous NAV CSV rows")
        try:
            observed = date.fromisoformat(row["date"])
        except (TypeError,ValueError) as e:
            raise ValueError("invalid original NAV source date") from e
        if observed in seen_dates:
            raise ValueError("duplicated original NAV source day")
        seen_dates.add(observed)
        value = _positive(row["nav_usd"], "source NAV USD")
        month = observed.strftime("%Y-%m")
        previous = parsed.get(month)
        if previous is None or observed > previous[0]:
            parsed[month] = (observed, value)
    for row in monthly:
        if not isinstance(row, dict) or row.get("month") not in parsed:
            raise ValueError("NAV month absent from original export")
        expected_day, expected_price = parsed[row["month"]]
        if (row.get("observed_for") != expected_day.isoformat()
                or _positive(row.get("nav_usd"), "NAV manifest USD")
                   != expected_price):
            raise ValueError("NAV manifest cannot be reproduced from original source bytes")
    _verify_digest(nbp_document)
    if (nbp_document.get("source") != "NBP_OFFICIAL_API"
            or nbp_document.get("data_kind") != "NON_EXECUTABLE_REFERENCE_ONLY"
            or nbp_document.get("historical_vintage_verified") is not False
            or nbp_document.get("series_contract",{}).get("usdpln",{}).get("return_basis") != "FX_RATE"):
        raise ValueError("not NBP official FX_RATE research evidence")
    fx = nbp_document.get("monthly_observations", {}).get("usdpln")
    if not isinstance(fx, list):
        raise ValueError("missing NBP official FX observations")
    source_windows = nbp_document.get("source_windows", [])
    receipts = []
    for window in source_windows:
        start = date.fromisoformat(window["from"])
        end = date.fromisoformat(window["to"])
        receipt = window["receipts"]["fx"]
        u = urlsplit(receipt["url"])
        if u.scheme != "https" or u.hostname != "api.nbp.pl" or not HEX64.fullmatch(receipt["sha256"]):
            raise ValueError("invalid official NBP receipt")
        receipts.append((start, end, receipt))
    fx_by_month = {}
    for row in fx:
        month = row["month"]
        if month in fx_by_month:
            raise ValueError("duplicate NBP calendar month")
        day = date.fromisoformat(row["observed_for"])
        if day.strftime("%Y-%m") != month:
            raise ValueError("NBP source month/date mismatch")
        matches = [rec for start,end,rec in receipts
                   if start <= day <= end
                   and row["source_url"] == rec["url"]
                   and row["raw_sha256"] == rec["sha256"]
                   and row["retrieved_at"] == rec["retrieved_at"]]
        if len(matches) != 1:
            raise ValueError("NBP reference does not match source receipt")
        _positive(row["value"], "NBP USDPLN")
        fx_by_month[month] = row
    converted = []
    previous_month = None
    for r in monthly:
        if not isinstance(r, dict) or set(r) != {"month", "observed_for", "nav_usd"}:
            raise ValueError("ambiguous NAV observation schema")
        month_date = _month_start(r["month"])
        if previous_month is not None and month_date != _next_month(previous_month):
            raise ValueError("NAV months have gaps")
        previous_month = month_date
        day = date.fromisoformat(r["observed_for"])
        if day.strftime("%Y-%m") != r["month"] or day.day < 20:
            raise ValueError("NAV month/date mismatch")
        nav_usd = _positive(r["nav_usd"], "Vanguard NAV USD")
        nbp = fx_by_month.get(r["month"])
        if nbp is None:
            raise ValueError("missing official USDPLN month " + r["month"])
        if nbp["observed_for"] != r["observed_for"]:
            raise ValueError("EXACT_DATE_FX_MISSING: " + r["month"] + " NAV "
                             + r["observed_for"] + " vs NBP " + nbp["observed_for"])
        fx_rate = _positive(nbp["value"], "NBP USDPLN")
        converted.append({
            "month": r["month"], "observed_for": r["observed_for"],
            "vanguard_acc_nav_usd": str(nav_usd),
            "nbp_usdpln": str(fx_rate),
            "nav_reference_pln": format(nav_usd * fx_rate, "f"),
            "vanguard_raw_export_sha256": digest,
            "nbp_source_url": nbp["source_url"],
            "nbp_raw_response_sha256": nbp["raw_sha256"],
        })
    result = {
        "status": "NAV_PLN_REFERENCE_ONLY_NOT_EXECUTABLE",
        "isin": ISIN, "calendar_months": len(converted),
        "first_month": converted[0]["month"], "last_month": converted[-1]["month"],
        "source_nav_sha256": digest,
        "source_nbp_sha256": nbp_document["evidence_sha256"],
        "series_name": "VANGUARD_ACC_NAV_REFERENCE_PLN",
        "return_basis": "ACCUMULATING_FUND_NAV_REFERENCE",
        "instrument_kind": "NON_EXECUTABLE_NAV_REFERENCE",
        "observations": converted,
        "first_publication_timestamps_certified": False,
        "historical_pit_certified": False,
        "trading_fill_prices_verified": False,
        "mapped_to_GLOBAL_EQUITY_TR_PLN": False,
        "real_backtest": "NOT_RUN_SOURCE_REFERENCE_ONLY",
        "financial_operations": 0, "paper_events_created": 0
    }
    result["evidence_sha256"] = _digest(result)
    return result
