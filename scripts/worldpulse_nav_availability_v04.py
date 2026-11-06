"""Read-only candidate NAV source probe for WorldPulse.ai (NOT world-pulse.io).

An audit, never an accepted data adapter. It fetches exact advertised
public JSON/CSV endpoints for ISIN IE00BK5BQT80 without logins/cookies,
records only transport, format, source-byte SHA-256, and date coverage
metadata. NEVER persists provider raw NAV values, trades, alters Neon, or
certifies rights from a successful HTTP response.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ISIN = "IE00BK5BQT80"
CANONICAL = "ie00bk5bqt80-nav"
BASE = "https://api.worldpulse.ai/api/v1/timeseries/canonical/" + CANONICAL
URLS = {"json": BASE, "csv": BASE + "/csv"}
MAX_BODY = 8_000_000
MIN_MONTHS = 36
DATE_KEYS = ("date", "observation_date", "period", "timestamp")
VALUE_KEYS = ("value", "nav", "nav_usd", "net_asset_value")
ROW_CONTAINERS = ("observations", "data", "values", "results", "points")


def _expected_origin(url):
    u = urlsplit(url)
    if (u.scheme != "https" or u.hostname != "api.worldpulse.ai"
            or u.username or u.password or u.fragment
            or u.path not in (
                "/api/v1/timeseries/canonical/" + CANONICAL,
                "/api/v1/timeseries/canonical/" + CANONICAL + "/csv",
            )):
        raise ValueError("unexpected WorldPulse financial API URL")


def _utc(clock):
    x = clock()
    if not isinstance(x, datetime) or x.tzinfo is None or x.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError("UTC-aware clock required")
    return x.isoformat()


def _fetch(url):
    _expected_origin(url)
    req = Request(url, headers={
        "Accept": "application/json, text/csv;q=0.9",
        "User-Agent": "ISL-public-financial-source-availability-audit/0.4",
    })
    try:
        with urlopen(req, timeout=20) as r:
            _expected_origin(r.geturl())
            body = r.read(MAX_BODY + 1)
            return r.status, r.headers.get("Content-Type", ""), body
    except HTTPError as exc:
        # Only status metadata is recorded for non-200 responses.
        return exc.code, exc.headers.get("Content-Type", "") if exc.headers else "", b""


def _rows_from_json(obj):
    if isinstance(obj, list):
        return obj
    if not isinstance(obj, dict):
        raise ValueError("JSON root not object or list")
    if isinstance(obj.get("data"), dict):
        return _rows_from_json(obj["data"])
    for key in ROW_CONTAINERS:
        val = obj.get(key)
        if isinstance(val, list):
            return val
    raise ValueError("no recognized JSON observations array")


def _month_sequence(first="2021-11", last="2026-10"):
    lo, hi = date.fromisoformat(first + "-01"), date.fromisoformat(last + "-01")
    result = []
    while lo <= hi:
        result.append(lo.strftime("%Y-%m"))
        lo = date(lo.year + (lo.month == 12), lo.month % 12 + 1, 1)
        if len(result) > 120:
            raise ValueError("unbounded target period")
    return result


def _date_value(row):
    if not isinstance(row, dict):
        raise ValueError("observation must be an object")
    d = next((row[key] for key in DATE_KEYS if key in row), None)
    v = next((row[key] for key in VALUE_KEYS if key in row), None)
    if d is None or v is None:
        raise ValueError("row missing unambiguous date/value")
    if not isinstance(d, str):
        raise ValueError("date string expected")
    # Only ISO date and ISO timestamp are accepted.
    day = date.fromisoformat(d[:10])
    if not isinstance(v, (str, int, float)) or isinstance(v, bool):
        raise ValueError("invalid NAV type")
    try:
        x = Decimal(str(v))
    except InvalidOperation as exc:
        raise ValueError("invalid NAV decimal") from exc
    if not x.is_finite() or x <= 0:
        raise ValueError("invalid NAV value")
    return day, x


def _parse_csv(body):
    try:
        txt = body.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("not UTF-8 CSV") from exc
    rd = csv.DictReader(StringIO(txt))
    if not rd.fieldnames or len(rd.fieldnames) > 25:
        raise ValueError("invalid CSV header")
    rows = list(rd)
    if len(rows) > 10000:
        raise ValueError("unbounded CSV observations")
    return rows


def assess_response(kind, status, ctype, body, *, clock=lambda: datetime.now(timezone.utc)):
    if kind not in URLS:
        raise ValueError("unexpected source kind")
    report = {
        "kind": kind,
        "url": URLS[kind],
        "checked_at": _utc(clock),
        "http_status": status,
        "content_type": ctype[:100] if isinstance(ctype, str) else None,
        "bytes": len(body),
        "sha256": sha256(body).hexdigest() if body else None,
        "availability": "BLOCKED",
        "schema_status": "NOT_CHECKED",
        "observations": 0,
        "unique_months": 0,
        "required_window_months": len(_month_sequence()),
        "in_window_months": 0,
        "missing_month_count": len(_month_sequence()),
        "earliest_observation_date": None,
        "latest_observation_date": None,
        "latest_target_month_present": False,
        "raw_values_saved": False,
        "rights_verified": False,
        "fund_isin_verified_against_issuer": False,
        "research_backtest": "NOT_RUN",
        "financial_operations": 0,
    }
    if status != 200:
        report["schema_status"] = "HTTP_NOT_200"
        return report
    if not isinstance(body, bytes) or len(body) > MAX_BODY or len(body) == 0:
        report["schema_status"] = "BAD_BODY_SIZE"
        return report
    try:
        if kind == "json":
            if "json" not in ctype.lower():
                raise ValueError("JSON expected")
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                # Identify explicit provider metadata when present, but
                # do NOT treat an absent/matching ISIN as independent proof.
                report["provider_identity_claim"] = str(parsed.get("isin", ""))[:24] or None
                if report["provider_identity_claim"] not in (None, ISIN, ISIN.lower()):
                    raise ValueError("API top-level ISIN mismatches target")
            rows = _rows_from_json(parsed)
        else:
            if not any(x in ctype.lower() for x in ("csv", "text/plain", "octet-stream")):
                raise ValueError("CSV expected")
            rows = _parse_csv(body)
        if len(rows) > 10000:
            raise ValueError("too many candidate observations")
        seen = set()
        months = set()
        for row in rows:
            d, _ = _date_value(row)
            if d in seen:
                raise ValueError("duplicate source observation date")
            seen.add(d)
            months.add(d.strftime("%Y-%m"))
        required = set(_month_sequence())
        inside = required.intersection(months)
        report.update({
            "schema_status": "RECOGNIZED_CANDIDATE_FORMAT",
            "observations": len(rows),
            "unique_months": len(months),
            "in_window_months": len(inside),
            "missing_month_count": len(required - inside),
            "earliest_observation_date": min(seen).isoformat() if seen else None,
            "latest_observation_date": max(seen).isoformat() if seen else None,
            "latest_target_month_present": _month_sequence()[-1] in months,
            "availability": ("DATA_COVERAGE_CANDIDATE_RIGHTS_UNVERIFIED"
                             if len(inside) >= MIN_MONTHS else "BLOCKED"),
        })
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        report["schema_status"] = "UNVERIFIED_SCHEMA"
        report["failure_type"] = type(exc).__name__
    return report


def audit(*, fetch=_fetch, clock=lambda: datetime.now(timezone.utc)):
    results = {}
    for kind, url in URLS.items():
        try:
            _expected_origin(url)
            status, ctype, raw = fetch(url)
            results[kind] = assess_response(kind, status, ctype, raw, clock=clock)
        except (OSError, ValueError, URLError) as exc:
            results[kind] = {
                "kind": kind, "url": url, "checked_at": _utc(clock),
                "availability": "BLOCKED", "schema_status": "TRANSPORT_ERROR",
                "failure_type": type(exc).__name__, "raw_values_saved": False,
                "rights_verified": False, "research_backtest": "NOT_RUN",
                "financial_operations": 0,
            }
    return {
        "provider": "worldpulse.ai",
        "not_same_as": "world-pulse.io",
        "isin": ISIN,
        "status": "SOURCE_NOT_ACCEPTED_LICENSE_AND_ISSUER_VALIDATION_REQUIRED",
        "results": results,
        "rights_to_store_raw_source": "UNVERIFIED",
        "rights_to_redistribute_raw_source": "UNVERIFIED",
        "issuing_provider_nav_match": "UNVERIFIED",
        "trading_price_certified": False,
        "research_backtest": "NOT_RUN",
        "paper_events_created": 0, "financial_operations": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    data = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    # Never print original observations or write source bytes.
    print("WORLDPULSE_NAV_AUDIT=" + json.dumps(data, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
