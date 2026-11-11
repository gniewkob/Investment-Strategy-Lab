"""Eurostat HICP Poland (ECOICOP v2) as MACRO_CONTEXT_REFERENCE only.

Public Eurostat Statistics API, dataset prc_hicp_minr (2026-current).
This is a consumer price index, never a financial total-return index.
An explicit --fetch-official performs ONE bounded read-only Eurostat HTTPS GET.
Default offline mode consumes a local JSON-stat 2.0 export; no credentials,
wallet, brokerage, orders, schedules, external DB or downstream decision calls.

Current-vintage index levels must never be described as first-published or PIT.
First-published dataset prc_hicp_fpd is separate and NOT silently combined.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import (
    HTTPRedirectHandler, HTTPSHandler, Request, build_opener,
)

DATASET = "prc_hicp_minr"
ROOT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/" + DATASET
DIMENSIONS = ("freq", "unit", "coicop18", "geo", "time")
FIXED = {"freq": "M", "unit": "I25", "coicop18": "TOTAL", "geo": "PL"}
MAX_BYTES = 1_000_000
MAX_MONTHS = 120
MONTH = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")

class HICPContextError(ValueError):
    pass


def _month(value: object) -> date:
    if not isinstance(value, str) or not MONTH.fullmatch(value):
        raise HICPContextError("year-month YYYY-MM required")
    try:
        return date.fromisoformat(value + "-01")
    except ValueError as exc:
        raise HICPContextError("invalid calendar month") from exc


def _next_month(value: date) -> date:
    return date(value.year + (value.month == 12),
                1 if value.month == 12 else value.month + 1, 1)


def _json(data: object) -> bytes:
    try:
        raw = json.dumps(data, ensure_ascii=True, allow_nan=False,
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, RecursionError, OverflowError) as exc:
        raise HICPContextError("finite JSON-stat input required") from exc
    if len(raw) > MAX_BYTES:
        raise HICPContextError("source payload exceeds read-only limit")
    return raw


def _read(path: Path) -> object:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise HICPContextError("bounded regular offline JSON-stat file required")
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        raise HICPContextError("oversized JSON-stat payload")
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HICPContextError("invalid Eurostat JSON-stat payload") from exc
    _json(data)
    return data


def _query(since: str, until: str) -> str:
    a, b = _month(since), _month(until)
    length = (b.year - a.year) * 12 + b.month - a.month + 1
    if not 1 <= length <= MAX_MONTHS or b > date.today().replace(day=1):
        raise HICPContextError("bounded, non-future HICP month window required")
    return ROOT + "?" + urlencode({
        "geo": "PL", "freq": "M", "coicop18": "TOTAL",
        "unit": "I25", "sinceTimePeriod": since, "untilTimePeriod": until,
        "lang": "EN",
    })


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise HICPContextError("cross-URL redirect prohibited")


def _fetch(url: str) -> object:
    if not url.startswith(ROOT + "?"):
        raise HICPContextError("only official fixed Eurostat dataset supported")
    opener = build_opener(_NoRedirect(), HTTPSHandler())
    request = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "Investment-Strategy-Lab-HICP-macro-research/0.1",
    })
    try:
        with opener.open(request, timeout=15) as response:
            if response.status != 200:
                raise HICPContextError("official endpoint did not return HTTP 200")
            if not (response.headers.get("Content-Type", "").lower()
                    .startswith(("application/json", "application/vnd.sdmx"))):
                raise HICPContextError("official API did not return JSON")
            body = response.read(MAX_BYTES + 1)
    except (OSError, TimeoutError) as exc:
        raise HICPContextError("Eurostat read-only fetch failed") from exc
    if len(body) > MAX_BYTES:
        raise HICPContextError("official response exceeds bounded read")
    try:
        data = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HICPContextError("Eurostat returned invalid JSON") from exc
    _json(data)
    return data


def _positions(index: object, count: int, label: str) -> dict[str, int]:
    if not isinstance(index, dict) or len(index) != count:
        raise HICPContextError(label + ": missing/extra categorical entries")
    if (any(not isinstance(k, str) or type(v) is not int
            for k, v in index.items())
            or set(index.values()) != set(range(count))):
        raise HICPContextError(label + ": invalid JSON-stat category positions")
    return index


def _payload_values(data: object, since: str, until: str) -> tuple[list[dict], str]:
    _json(data)
    if (not isinstance(data, dict)
            or data.get("version") != "2.0" or data.get("class") != "dataset"
            or data.get("source") not in ("ESTAT", "Eurostat")):
        raise HICPContextError("expected official Eurostat JSON-stat 2.0 dataset")
    ids = data.get("id")
    sizes = data.get("size")
    dims = data.get("dimension")
    if (not isinstance(ids, list) or set(ids) != set(DIMENSIONS)
            or len(ids) != len(DIMENSIONS)
            or not isinstance(sizes, list) or len(sizes) != len(ids)
            or not isinstance(dims, dict) or set(dims) != set(ids)
            or any(type(s) is not int or not 1 <= s <= MAX_MONTHS for s in sizes)):
        raise HICPContextError("exact HICP dimensions and bounded shape required")
    categories: dict[str, dict[str, int]] = {}
    for name, size in zip(ids, sizes):
        dimension = dims[name]
        if not isinstance(dimension, dict):
            raise HICPContextError("invalid dimension metadata")
        cats = dimension.get("category")
        if not isinstance(cats, dict):
            raise HICPContextError("missing category metadata")
        categories[name] = _positions(cats.get("index"), size, name)
        if name in FIXED and categories[name] != {FIXED[name]: 0}:
            raise HICPContextError(name + ": unexpected unit/country/measure")
    times = categories["time"]
    if not 1 <= len(times) <= MAX_MONTHS:
        raise HICPContextError("empty/oversized monthly series")
    a, b = _month(since), _month(until)
    ordered = sorted(times.items(), key=lambda pair: pair[1])
    if any(not a <= _month(month) <= b for month, _ in ordered):
        raise HICPContextError("response includes values outside query window")
    for i in range(1, len(ordered)):
        if _next_month(_month(ordered[i - 1][0])) != _month(ordered[i][0]):
            raise HICPContextError("unexpected chronological gaps in indexed dates")
    if _month(ordered[0][0]) != a or _month(ordered[-1][0]) != b:
        raise HICPContextError("response does not cover requested monthly window")

    positions = [categories[name].get(FIXED[name], 0) if name != "time"
                 else 0 for name in ids]
    if any(position is None for position in positions):
        raise HICPContextError("invalid fixed series position")
    value_map = data.get("value")
    status_map = data.get("status", {})
    total = 1
    for size in sizes:
        total *= size
    if not isinstance(value_map, (dict, list)) or not isinstance(status_map, dict):
        raise HICPContextError("JSON-stat values or status malformed")
    if isinstance(value_map, list) and len(value_map) != total:
        raise HICPContextError("dense data vector length mismatch")
    if isinstance(value_map, dict) and any(
            not isinstance(k, str) or not k.isdigit() or not 0 <= int(k) < total
            for k in value_map):
        raise HICPContextError("invalid sparse index positions")
    result = []
    for month, idx in ordered:
        coords = list(positions)
        coords[ids.index("time")] = idx
        offset = 0
        for coordinate, size in zip(coords, sizes):
            offset = offset * size + coordinate
        value = (value_map[offset] if isinstance(value_map, list)
                 else value_map.get(str(offset)))
        flag = status_map.get(str(offset))
        if flag is not None and (not isinstance(flag, str) or len(flag) > 12):
            raise HICPContextError("invalid Eurostat observation flag")
        if value is None:
            result.append({"month": month, "index_2025_100": None,
                           "status": flag or "MISSING"})
            continue
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise HICPContextError("unexpected index value type")
        try:
            number = Decimal(str(value))
        except (ValueError, InvalidOperation) as exc:
            raise HICPContextError("invalid index number") from exc
        if not number.is_finite() or number <= 0:
            raise HICPContextError("non-positive or non-finite HICP")
        result.append({"month": month, "index_2025_100": str(number),
                       "status": flag})
    return result, str(data.get("updated", "NOT_PROVIDED"))


def inspect_hicp(data: object, *, since: str, until: str, retrieval_scope: str) -> dict:
    """Retrospective macro-only receipt; never usable as historical PIT or TR."""
    if retrieval_scope not in ("LOCAL_OFFLINE_REVIEW", "EUROSTAT_PUBLIC_READ_ONLY"):
        raise HICPContextError("unknown retrieval scope")
    _query(since, until)
    rows, provider_updated = _payload_values(data, since, until)
    missing = [x["month"] for x in rows if x["index_2025_100"] is None]
    receipt = {
        "schema": "ISL_EUROSTAT_HICP_PL_MACRO_CONTEXT_V01",
        "status": "AVAILABLE_CONTEXT_NOT_HISTORICAL_PIT" if not missing
                  else "BLOCKED_INCOMPLETE_CONTEXT",
        "source": "Eurostat",
        "dataset": DATASET,
        "dataflow_semantics": "ECOICOP_V2_ALL_ITEMS_HICP",
        "indicator_type": "CONSUMER_PRICE_INDEX",
        "measure_unit": "I25_INDEX_2025_100",
        "country": "PL", "frequency": "M",
        "source_attribution": "Source: Eurostat, prc_hicp_minr; accessed by the reviewer",
        "provider_reported_last_update": provider_updated,
        "retrieval_scope": retrieval_scope,
        "source_payload_canonical_sha256": sha256(_json(data)).hexdigest(),
        "observed_month_count": len(rows),
        "available_month_count": len(rows) - len(missing),
        "missing_months": missing,
        "observations": rows,
        "price_index_as_asset_return": False,
        "historical_first_release_captured": False,
        "historical_point_in_time_certified": False,
        "first_released_fpd_reconciled": False,
        "qualified_model_series": [],
        "paper_candidates": [],
        "model_state": "HOLD_CASH",
        "source_manifest_created": False,
        "financial_operations": 0,
        "orders_sent": 0,
        "database_writes": 0,
        "paper_fills": 0,
    }
    receipt["receipt_sha256"] = sha256(_json(receipt)).hexdigest()
    return receipt


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--input-local-json", type=Path)
    src.add_argument("--fetch-official", action="store_true")
    p.add_argument("--since", required=True, help="YYYY-MM")
    p.add_argument("--until", required=True, help="YYYY-MM")
    args = p.parse_args()
    url = _query(args.since, args.until)
    data = _fetch(url) if args.fetch_official else _read(args.input_local_json)
    report = inspect_hicp(
        data, since=args.since, until=args.until,
        retrieval_scope="EUROSTAT_PUBLIC_READ_ONLY" if args.fetch_official
                        else "LOCAL_OFFLINE_REVIEW")
    print("ISL_EUROSTAT_HICP_CONTEXT=" +
          json.dumps(report, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
