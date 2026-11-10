"""Eurostat public HICP first-available-final vs latest *revision research*.

Compares first-release archive prc_hicp_fpd, release FIN = Final (verified by
official API schema 2026-11-10), with prc_hicp_minr current-vintage, for
exactly matching PL/M/TOTAL/I25, month-by-month. FLS = Flash is NOT used.

This is an inflation index comparison, NEVER an asset return or investment
signal. It does not independently certify historical first-publication time.
No database, broker/wallet, paper candidate, trading or scheduled collection.
Default CLI is offline. Explicit --fetch-official does exactly TWO
authenticated-free HTTPS GETs to fixed Eurostat public endpoints, bounded.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, HTTPSHandler, HTTPRedirectHandler, build_opener
from urllib.error import HTTPError, URLError

from scripts.eurostat_hicp_macro_context_v01 import (
    HICPContextError, _json as canonical_current, _read as read_current,
    _query as current_url, _fetch as fetch_current,
    _payload_values as latest_values, _month, _next_month,
)
from scripts.eurostat_hicp_fpd_schema_probe_v01 import (
    API_ROOT as FPD_URL_ROOT, FPDProbeError,
    _canonical as canonical_fpd, _category_index as category_index,
    _read_offline as read_fpd,
)

SCHEMA = "ISL_EUROSTAT_HICP_PL_FIRST_FINAL_REVISION_RESEARCH_V01"
FIXED = {"freq": "M", "unit": "I25", "coicop18": "TOTAL", "geo": "PL"}
RELEASE_LABELS = {"FIN": "Final", "FLS": "Flash"}
FPD_IDS = frozenset((*FIXED, "release", "time"))
MAX_MONTHS = 24
KNOWN_FPD_EXCEPTION_MONTH = "2026-01"
FIRST_SUPPORTED_OBSERVATION = "2026-01"
MAX_FPD_RESPONSE_BYTES = 2_000_000


class HICPRevisionError(ValueError):
    pass


def _canonical(obj):
    return canonical_fpd(obj)


def _window(since, until):
    try:
        a, b = _month(since), _month(until)
        current_url(since, until)
    except HICPContextError as exc:
        raise HICPRevisionError("invalid requested time range") from exc
    span = (b.year - a.year) * 12 + b.month - a.month + 1
    if not 1 <= span <= MAX_MONTHS or since < FIRST_SUPPORTED_OBSERVATION:
        raise HICPRevisionError("1–24 contiguous months from 2026-01 required")
    return a, b, span


def _timestamp_utc(raw):
    if not isinstance(raw, str):
        raise HICPRevisionError("explicit UTC observation timestamp required")
    try:
        timestamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HICPRevisionError("invalid observation timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
        raise HICPRevisionError("observation timestamp must be UTC")
    return timestamp.astimezone(timezone.utc).isoformat()


def _positions(index):
    labels = category_index(index)
    return {code: i for i, code in enumerate(labels)}


def _fpd_final_values(payload, since, until):
    """Parse verified FIN/Final dimension; never infer releases from time keys."""
    try:
        _canonical(payload)
    except FPDProbeError as exc:
        raise HICPRevisionError("invalid bounded FPD input JSON") from exc
    if (not isinstance(payload, dict) or payload.get("class") != "dataset"
            or str(payload.get("version")) != "2.0"
            or payload.get("source") not in ("ESTAT", "Eurostat")):
        raise HICPRevisionError("official-style Eurostat FPD JSON-stat required")
    ids, sizes, dims = (payload.get("id"), payload.get("size"),
                        payload.get("dimension"))
    if (not isinstance(ids, list) or len(ids) != 6
            or set(ids) != FPD_IDS or len(ids) != len(set(ids))
            or not isinstance(sizes, list) or len(sizes) != len(ids)
            or not isinstance(dims, dict) or set(dims) != set(ids)):
        raise HICPRevisionError("FPD six-dimensional schema mismatch")
    catalog = {}
    for name, size in zip(ids, sizes):
        if type(size) is not int or not 1 <= size <= MAX_MONTHS:
            raise HICPRevisionError("FPD axis cardinality invalid")
        dim = dims.get(name)
        if not isinstance(dim, dict) or not isinstance(dim.get("category"), dict):
            raise HICPRevisionError("missing FPD dimension metadata")
        try:
            position = _positions(dim["category"].get("index"))
        except FPDProbeError as exc:
            raise HICPRevisionError("invalid FPD category index positions") from exc
        if len(position) != size:
            raise HICPRevisionError("FPD category cardinality mismatch")
        catalog[name] = position
        if name in FIXED and position != {FIXED[name]: 0}:
            raise HICPRevisionError(name + ": FPD geo/measure/unit mismatch")
    if catalog["release"] != {"FIN": 0, "FLS": 1} and set(catalog["release"]) != set(RELEASE_LABELS):
        raise HICPRevisionError("actual FIN/FLS release axis not recognised")
    cat_labels = dims["release"]["category"].get("label", {})
    if not isinstance(cat_labels, dict) or any(
            cat_labels.get(k) != v for k, v in RELEASE_LABELS.items()):
        raise HICPRevisionError("official FIN/FLS category labels not matched")

    first, last, count = _window(since, until)
    timeline = sorted(catalog["time"].items(), key=lambda pair: pair[1])
    if len(timeline) != count:
        raise HICPRevisionError("FPD time window incomplete")
    expected = first
    for period, _ in timeline:
        if _month(period) != expected:
            raise HICPRevisionError("FPD month gap or incorrect requested window")
        expected = _next_month(expected)

    values, flags = payload.get("value"), payload.get("status", {})
    total = 1
    for size in sizes:
        total *= size
    if not isinstance(values, (dict, list)) or not isinstance(flags, dict):
        raise HICPRevisionError("FPD value/status not JSON-stat structures")
    if isinstance(values, list) and len(values) != total:
        raise HICPRevisionError("FPD dense value vector length wrong")
    if isinstance(values, dict) and any(
            not isinstance(k, str) or not k.isdigit()
            or not 0 <= int(k) < total for k in values):
        raise HICPRevisionError("FPD sparse value key invalid")
    if any(not isinstance(k, str) or not k.isdigit()
           or not 0 <= int(k) < total
           or not isinstance(v, str) or len(v) > 12
           for k, v in flags.items()):
        raise HICPRevisionError("FPD status key/flag invalid")

    rows = []
    for month, month_pos in timeline:
        positions = {
            **{name: catalog[name][value] for name, value in FIXED.items()},
            "release": catalog["release"]["FIN"],
            "time": month_pos,
        }
        offset = 0
        for dim_name, size in zip(ids, sizes):
            offset = offset * size + positions[dim_name]
        number = values[offset] if isinstance(values, list) else values.get(str(offset))
        flag = flags.get(str(offset))
        if number is None:
            rows.append({"month": month, "level": None, "flag": flag})
            continue
        if type(number) not in (int, float, str):
            raise HICPRevisionError("invalid FPD index level")
        try:
            level = Decimal(str(number))
        except (ValueError, InvalidOperation) as exc:
            raise HICPRevisionError("unparseable FPD index value") from exc
        if not level.is_finite() or level <= 0:
            raise HICPRevisionError("FPD index level not finite/positive")
        rows.append({"month": month, "level": level, "flag": flag})
    return rows


def _decimal(value):
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise HICPRevisionError("invalid latest index level") from exc
    if not result.is_finite() or result <= 0:
        raise HICPRevisionError("invalid latest index level")
    return result


def _plain(value):
    return format(value, "f") if value is not None else None


def compare_revisions(fpd, latest, *, since, until, observed_at_utc):
    """Compute index-point *revisions*, not market returns or signals."""
    a, b, count = _window(since, until)
    observed_at = _timestamp_utc(observed_at_utc)
    fpd_rows = _fpd_final_values(fpd, since, until)
    try:
        current_rows, updated = latest_values(latest, since, until)
    except HICPContextError as exc:
        raise HICPRevisionError("invalid matching latest-vintage HICP source") from exc
    if len(fpd_rows) != count or len(current_rows) != count:
        raise HICPRevisionError("mismatched source coverage")
    rows = []
    used = []
    missing = []
    exception_months = []
    for first_row, new_row in zip(fpd_rows, current_rows):
        month = first_row["month"]
        if new_row["month"] != month:
            raise HICPRevisionError("FPD/latest time dimensions do not align")
        final_level = first_row["level"]
        current_level = _decimal(new_row["index_2025_100"])
        is_exception = month == KNOWN_FPD_EXCEPTION_MONTH
        if is_exception:
            exception_months.append(month)
        unavailable = final_level is None or current_level is None
        if unavailable:
            missing.append(month)
        delta = (current_level - final_level) if not unavailable else None
        if not unavailable and not is_exception:
            used.append(delta)
        rows.append({
            "month": month,
            "comparison_status": ("MISSING_SOURCE_OBSERVATION" if unavailable else
                                  "KNOWN_FPD_ARCHIVE_RESTORATION_REVIEW" if is_exception else
                                  "COMPARABLE_LATEST_MINUS_FIRST_FINAL"),
            "first_release_kind": "FIN_FINAL",
            "first_final_flag": first_row["flag"],
            "latest_flag": new_row["status"],
            "revision_index_points": _plain(delta),
            "included_in_revision_summary": not unavailable and not is_exception,
            "first_publication_timestamp_proven": False,
        })
    if missing:
        status = "BLOCKED_INCOMPLETE_REVISIONS"
    elif exception_months:
        status = "REVIEW_REQUIRED_KNOWN_JAN_2026_FPD_EXCEPTION"
    else:
        status = "REVISION_COMPARISON_RESEARCH_ONLY"
    output = {
        "schema": SCHEMA,
        "status": status,
        "source": "Eurostat",
        "country": "PL",
        "frequency": "M",
        "coicop18": "TOTAL",
        "unit": "I25_INDEX_2025_100",
        "fpd_dataset": "prc_hicp_fpd",
        "fpd_release_category": "FIN",
        "excluded_fpd_release_category": "FLS",
        "latest_dataset": "prc_hicp_minr",
        "source_attribution": "Source: Eurostat, HICP first released and current monthly indices",
        "requested_from": since, "requested_to": until,
        "observed_at_utc": observed_at,
        "reported_latest_updated": updated,
        "fpd_canonical_sha256": sha256(canonical_fpd(fpd)).hexdigest(),
        "latest_canonical_sha256": sha256(canonical_current(latest)).hexdigest(),
        "month_count": count,
        "comparable_month_count": len(used),
        "missing_months": missing,
        "exception_months": exception_months,
        "nonzero_revision_months": sum(1 for v in used if v != 0),
        "max_absolute_revision_index_points": _plain(max(map(abs, used), default=Decimal(0))),
        "rows": rows,
        "revision_not_investment_return": True,
        "historical_first_published_instant_authenticated": False,
        "full_historical_vintage_sequence_available": False,
        "historical_point_in_time_certified": False,
        "qualified_model_series": [],
        "paper_candidates": [],
        "source_manifest_created": False,
        "market_execution_authorized": False,
        "model_state": "HOLD_CASH",
        "orders_sent": 0,
        "paper_fills": 0,
        "database_writes": 0,
        "financial_operations": 0,
    }
    output["receipt_sha256"] = sha256(_canonical(output)).hexdigest()
    return output


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HICPRevisionError("Eurostat redirect forbidden")


def _fetch_fpd(since, until):
    _window(since, until)
    params = {
        "geo": "PL", "freq": "M", "coicop18": "TOTAL",
        "unit": "I25", "sinceTimePeriod": since, "untilTimePeriod": until,
        "lang": "EN",
    }
    url = FPD_URL_ROOT + "?" + urlencode(params)
    opener = build_opener(_NoRedirect(), HTTPSHandler())
    try:
        with opener.open(Request(url, headers={
                "Accept": "application/json",
                "User-Agent": "Investment-Strategy-Lab-HICP-archive-revision-research/0.1",
        }), timeout=20) as reply:
            if reply.status != 200 or not reply.headers.get(
                    "Content-Type", "").lower().startswith(("application/json", "application/vnd.sdmx")):
                raise HICPRevisionError("official FPD response unavailable or non-JSON")
            raw = reply.read(MAX_FPD_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise HICPRevisionError("official FPD read-only source fetch failed") from exc
    if len(raw) > MAX_FPD_RESPONSE_BYTES:
        raise HICPRevisionError("official FPD response exceeds 2MB")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HICPRevisionError("official FPD response JSON invalid") from exc


def main():
    p = argparse.ArgumentParser(description=__doc__)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--fetch-official", action="store_true")
    src.add_argument("--fpd-local-json", type=Path)
    p.add_argument("--current-local-json", type=Path)
    p.add_argument("--since", required=True)
    p.add_argument("--until", required=True)
    p.add_argument("--observed-at-utc")
    args = p.parse_args()
    if args.fetch_official:
        if args.current_local_json is not None:
            p.error("--fetch-official forbids local current JSON")
        fpd = _fetch_fpd(args.since, args.until)
        try:
            latest = fetch_current(current_url(args.since, args.until))
        except HICPContextError as exc:
            raise HICPRevisionError("official current Eurostat HICP read failed") from exc
    else:
        if args.current_local_json is None:
            p.error("offline FPD and current JSON files required together")
        fpd = read_fpd(args.fpd_local_json)
        latest = read_current(args.current_local_json)
    at = args.observed_at_utc or datetime.now(timezone.utc).isoformat()
    report = compare_revisions(
        fpd, latest, since=args.since, until=args.until, observed_at_utc=at)
    print("ISL_HICP_FPD_REVISION_RESEARCH=" +
          json.dumps(report, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
