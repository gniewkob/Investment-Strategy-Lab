"""Collect historical official NBP FX and gold monthly REFERENCE evidence.

One official NBP API call covers no more than 93 days; this module fetches
contiguous <=90-day windows, preserving the SHA-256 and retrieval timestamp
of EVERY source response. Rows are the last ACTUALLY PUBLISHED quotation
in each month, not the calendar-month last date imputed by interpolation.

FX is NBP table A mid rate, gold NBP PLN/g PRICE_ONLY. Neither is an
executable investment price nor a PLN total-return series; this module
cannot emit GLOBAL_EQUITY_TR_PLN, PL_BONDS_TR_PLN or GOLD_TR_PLN.
It never accesses a database, broker, or financial account.
"""
from __future__ import annotations

import argparse
import calendar
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re

from scripts.nbp_reference_capture import capture

SERIES = ("usdpln", "eurpln", "gold")
SERIES_META = {
    "usdpln": {"instrument_code": "USDPLN_NBP", "return_basis": "FX_RATE"},
    "eurpln": {"instrument_code": "EURPLN_NBP", "return_basis": "FX_RATE"},
    "gold": {"instrument_code": "GOLD_NBP_PLN_G", "return_basis": "PRICE_ONLY"},
}
MONTH = re.compile(r"^[0-9]{4}-[0-9]{2}$")
WINDOW_DAYS = 90
MAX_MONTHS = 72


def _month(value: str) -> tuple[int, int]:
    if not isinstance(value, str) or not MONTH.fullmatch(value):
        raise ValueError("expected YYYY-MM")
    year, month = map(int, value.split("-"))
    if not (2013 <= year <= 2100 and 1 <= month <= 12):
        raise ValueError("NBP full-history request starts no earlier than 2013")
    return year, month


def _month_start(value: str) -> date:
    return date(*_month(value), 1)


def _month_end(value: str) -> date:
    y, m = _month(value)
    return date(y, m, calendar.monthrange(y, m)[1])


def _months(first: str, last: str) -> list[str]:
    a, b = _month(first), _month(last)
    if a > b:
        raise ValueError("start_month after end_month")
    result = []
    while a <= b:
        result.append(f"{a[0]:04d}-{a[1]:02d}")
        a = (a[0] + 1, 1) if a[1] == 12 else (a[0], a[1] + 1)
    if len(result) > MAX_MONTHS:
        raise ValueError("bounded request permits at most 72 months")
    return result


def _windows(start: date, end: date) -> list[tuple[date, date]]:
    result = []
    while start <= end:
        stop = min(start + timedelta(days=WINDOW_DAYS - 1), end)
        result.append((start, stop))
        start = stop + timedelta(days=1)
    return result


def _digest(rows: object) -> str:
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":"),
                     allow_nan=False).encode("utf-8")
    return sha256(raw).hexdigest()


def collect(start_month: str, end_month: str, *, fetch=None, clock=None) -> dict:
    months = _months(start_month, end_month)
    start = _month_start(months[0])
    end = _month_end(months[-1])
    now = clock() if clock is not None else datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("UTC clock with timezone required")
    now = now.astimezone(timezone.utc)
    if end > now.date():
        raise ValueError("monthly archive must contain only completed months")

    # Gather all evidence before selecting monthly observations.
    source_windows, observed, seen = [], {name: [] for name in SERIES}, {
        name: set() for name in SERIES}
    for begin, finish in _windows(start, end):
        options = {}
        if fetch is not None:
            options["fetch"] = fetch
        if clock is not None:
            options["clock"] = clock
        result = capture(begin.isoformat(), finish.isoformat(), **options)
        receipts = result["receipts"]
        if set(receipts) != {"fx", "gold"}:
            raise ValueError("incomplete FX/gold official evidence")
        source_windows.append({
            "from": begin.isoformat(), "to": finish.isoformat(),
            "receipts": receipts,
        })
        for name in SERIES:
            records = result["series"][name]
            if not records:
                raise ValueError("empty NBP series in window: " + name)
            for item in records:
                day = date.fromisoformat(item["observed_for"])
                if day < begin or day > finish or day > now.date():
                    raise ValueError("invalid observation date")
                if day in seen[name]:
                    raise ValueError("duplicate official date across windows")
                seen[name].add(day)
                if item["available_at"] is not None:
                    raise ValueError("unsupported fabricated first availability")
                expected_basis = ("PRICE_ONLY_PLN_PER_GRAM" if name == "gold"
                                  else "TABLE_A_MID_PLN_PER_FOREIGN_UNIT")
                if item["basis"] != expected_basis or item["currency"] != "PLN":
                    raise ValueError("unapproved quote or basis")
                raw_sha = item["source_sha256"]
                expected_kind = "gold" if name == "gold" else "fx"
                if raw_sha != receipts[expected_kind]["sha256"]:
                    raise ValueError("source digest does not match response")
                if item["source_url"] != receipts[expected_kind]["url"]:
                    raise ValueError("source URL does not match response")
                value = Decimal(item["value"])
                if not value.is_finite() or value <= 0:
                    raise ValueError("invalid NBP reference value")
                observed[name].append({
                    "observed_for": day.isoformat(),
                    "value": str(value),
                    "source_url": item["source_url"],
                    "raw_sha256": raw_sha,
                    "retrieved_at": item["retrieved_at"],
                })

    monthly = {}
    for name in SERIES:
        selected = {}
        for item in observed[name]:
            month = item["observed_for"][:7]
            if month in months and (month not in selected or
                                   item["observed_for"] > selected[month]["observed_for"]):
                selected[month] = item
        absent = sorted(set(months) - set(selected))
        if absent:
            raise ValueError(f"NBP series {name} lacks published month(s): {absent}")
        monthly[name] = [
            {"month": month, **selected[month]}
            for month in months
        ]

    result = {
        "source": "NBP_OFFICIAL_API",
        "data_kind": "NON_EXECUTABLE_REFERENCE_ONLY",
        "series_contract": SERIES_META,
        "first_month": start_month, "last_month": end_month,
        "calendar_months": len(months),
        "source_window_count": len(source_windows),
        "source_request_count": len(source_windows) * 2,
        "source_windows": source_windows,
        "monthly_observations": monthly,
        "monthly_counts": {name: len(rows) for name, rows in monthly.items()},
        "historical_first_publication_time_verified": False,
        "historical_vintage_verified": False,
        "point_in_time_backtest_authorized": False,
        "paper_events_created": 0,
        "financial_operations": 0,
        "backtest": "NOT_RUN_REFERENCE_ONLY",
    }
    result["evidence_sha256"] = _digest(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-month", required=True)
    parser.add_argument("--end-month", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = collect(args.start_month, args.end_month)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8")
    print("NBP_LONG_HISTORY_SUMMARY=" + json.dumps({
        "source": result["source"],
        "first_month": result["first_month"], "last_month": result["last_month"],
        "months": result["calendar_months"],
        "windows": result["source_window_count"],
        "requests": result["source_request_count"],
        "monthly_counts": result["monthly_counts"],
        "evidence_sha256": result["evidence_sha256"],
        "historical_vintage_verified": False,
        "backtest": result["backtest"],
        "financial_operations": 0,
    }, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
