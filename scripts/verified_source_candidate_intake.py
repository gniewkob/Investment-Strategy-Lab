"""Offline evidence intake for separately obtained Vanguard NAV and TBSP.Index data.

Not a data downloader or licence grant. Accepts human-mapped CSV from a
source-authorised research copy, preserving distinctions between fund NAV,
tradable ETF prices and an *uninvestable* government-bond return benchmark.
Every output remains unapproved for PIT backtesting and paper transactions.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlsplit

SOURCES = {
    "VANGUARD_ALL_WORLD_ACC_NAV_USD": {
        "hosts": frozenset(("www.vanguard.co.uk", "www.pl.vanguard", "global.vanguard.com")),
        "currency": "USD",
        "basis": "FUND_ACCUMULATING_NAV",
        "instrument_kind": "FUND_SHARE_CLASS_NAV",
        "identifier": "IE00BK5BQT80",
        "start": date(2019, 7, 23),
    },
    "BONDSPOT_TBSP_CLOSE_PLN": {
        "hosts": frozenset(("www.bondspot.pl", "bondspot.pl")),
        "currency": "PLN",
        "basis": "BOND_TOTAL_RETURN_BENCHMARK_INDEX",
        "instrument_kind": "NON_TRADABLE_INDEX",
        "identifier": "TBSP.Index",
        "start": date(2006, 12, 29),
    },
}
HEADER = ["date", "value"]


def _parse_date(value: str) -> date:
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("date must be ISO YYYY-MM-DD")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("date must be ISO YYYY-MM-DD")
    return parsed


def _parse_value(value: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError("value must be an ungrouped decimal string")
    # No thousand separators, commas, scientific notation or NaN.
    if value.count(".") > 1 or any(ch not in "0123456789." for ch in value):
        raise ValueError("value must use a dot decimal separator")
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise ValueError("invalid value") from None
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError("value must be finite and positive")
    return str(parsed)


def _gap_months(dates):
    buckets = {d.year * 12 + d.month for d in dates}
    start, end = min(buckets), max(buckets)
    missing = []
    for index in range(start, end + 1):
        if index not in buckets:
            year, month_zero = divmod(index - 1, 12)
            missing.append(f"{year:04d}-{month_zero + 1:02d}")
    return missing


def validate_mapped_series(raw: bytes, *, series_id: str, official_url: str,
                           retrieved_at: datetime, official_raw_bytes: bytes | None = None):
    """Validate only normalized research inputs, with no source entitlement claims."""
    if series_id not in SOURCES:
        raise ValueError("unknown source identity")
    spec = SOURCES[series_id]
    url = urlsplit(official_url)
    if url.scheme != "https" or url.hostname not in spec["hosts"]:
        raise ValueError("unexpected official HTTPS source host")
    if not isinstance(retrieved_at, datetime) or retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")
    if not isinstance(raw, bytes) or not raw:
        raise ValueError("nonempty UTF-8 normalized CSV required")
    if official_raw_bytes is not None and not isinstance(official_raw_bytes, bytes):
        raise ValueError("official_raw_bytes must be bytes")
    retrieved = retrieved_at.astimezone(timezone.utc)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("normalized CSV must be UTF-8") from None
    reader = csv.DictReader(io.StringIO(text), delimiter=",", strict=True)
    if reader.fieldnames != HEADER:
        raise ValueError("expected exact CSV header: date,value")
    values, seen = [], set()
    for row in reader:
        if None in row or set(row) != set(HEADER) or any(row[field] is None for field in HEADER):
            raise ValueError("malformed CSV row")
        observed = _parse_date(row["date"])
        if observed < spec["start"] or observed > retrieved.date():
            raise ValueError("date outside source history or after retrieval")
        if observed in seen:
            raise ValueError("duplicate observation date")
        seen.add(observed)
        values.append({"observed_for": observed.isoformat(), "value": _parse_value(row["value"])})
    if not values:
        raise ValueError("no observations")
    values.sort(key=lambda row: row["observed_for"])
    gaps = _gap_months([_parse_date(row["observed_for"]) for row in values])
    return {
        "series_id": series_id,
        "instrument_kind": spec["instrument_kind"],
        "identifier": spec["identifier"],
        "currency": spec["currency"],
        "basis": spec["basis"],
        "official_url": official_url,
        "retrieved_at": retrieved.isoformat(),
        "normalized_csv_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_source_sha256": (hashlib.sha256(official_raw_bytes).hexdigest()
                              if official_raw_bytes is not None else None),
        "raw_to_normalized_mapping_independently_verified": False,
        "source_entitlement_verified": False,
        "historical_vintage_verified": False,
        "historical_first_usable_at_verified": False,
        "market_calendar_verified": False,
        "no_monthly_observations": gaps,
        "daily_trading_session_coverage_verified": False,
        "observations": values,
        "observations_count": len(values),
        "status": "INSUFFICIENT_DATA",
        "backtest": "NOT_RUN",
        "paper_events_created": 0,
        "notes": (
            "Candidate history only; original publication/revision evidence and "
            "licence must be independently verified. Vanguard NAV is not ETF "
            "execution price; TBSP.Index is not a purchasable bond instrument."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapped_csv", type=Path)
    parser.add_argument("--series-id", choices=sorted(SOURCES), required=True)
    parser.add_argument("--official-url", required=True)
    parser.add_argument("--original-copy", type=Path)
    args = parser.parse_args()
    raw_original = args.original_copy.read_bytes() if args.original_copy else None
    print(json.dumps(validate_mapped_series(
        args.mapped_csv.read_bytes(), series_id=args.series_id,
        official_url=args.official_url, retrieved_at=datetime.now(timezone.utc),
        official_raw_bytes=raw_original
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
