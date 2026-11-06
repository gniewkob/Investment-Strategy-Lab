"""Strict offline normalization of a *manually reviewed* GUS monthly CPI export.

Input is NOT the GUS raw CSV format. A human must independently map the
'poprzedni miesiac = 100' portion to the three-column semicolon CSV contract:
year;month;previous_month_100
This module cannot establish first historical publication dates or reuse rights.
It never downloads data, writes a database, or creates paper transactions.
"""
from __future__ import annotations

import argparse
import calendar
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlsplit

FIELDS = ("year", "month", "previous_month_100")
OFFICIAL_HOSTS = frozenset(("stat.gov.pl", "publikacje.new.stat.gov.pl"))


def _date(value):
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("publication date must be YYYY-MM-DD")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("publication date must be YYYY-MM-DD")
    return parsed


def _time(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("retrieved_at requires a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def normalize(raw: bytes, *, official_publication_url: str,
              snapshot_published_on: str, retrieved_at: datetime) -> dict:
    """Create a non-authoritative validation receipt, not an approved CPI series."""
    if not isinstance(raw, bytes) or not raw:
        raise ValueError("nonempty normalized CSV bytes required")
    parsed_url = urlsplit(official_publication_url)
    if parsed_url.scheme != "https" or parsed_url.hostname not in OFFICIAL_HOSTS:
        raise ValueError("the GUS publication URL must be an official HTTPS host")
    snapshot = _date(snapshot_published_on)
    collected = _time(retrieved_at)
    if collected.date() < snapshot:
        raise ValueError("retrieval precedes publication snapshot")
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("normalized CSV must be UTF-8") from None
    reader = csv.DictReader(io.StringIO(decoded), delimiter=";", strict=True)
    if reader.fieldnames != list(FIELDS):
        raise ValueError("expected year;month;previous_month_100 CSV header")
    values, periods = [], set()
    for row in reader:
        if None in row or any(row.get(key) is None for key in FIELDS):
            raise ValueError("malformed row")
        y, m, index = (row[key].strip() for key in FIELDS)
        if len(y) != 4 or not y.isdecimal() or len(m) not in (1, 2) or not m.isdecimal():
            raise ValueError("invalid year/month")
        year, month = int(y), int(m)
        if not 1982 <= year <= 2100 or not 1 <= month <= 12:
            raise ValueError("out-of-range year/month")
        point = date(year, month, calendar.monthrange(year, month)[1])
        if point > snapshot:
            raise ValueError("observation period ends after source snapshot")
        key = point.isoformat()
        if key in periods:
            raise ValueError("duplicate CPI month")
        periods.add(key)
        # The reviewed input uses Polish decimal commas, never thousands separators.
        if any(ch not in "0123456789,." for ch in index) or ("," in index and "." in index):
            raise ValueError("invalid decimal syntax")
        try:
            v = Decimal(index.replace(",", "."))
        except InvalidOperation:
            raise ValueError("invalid CPI value") from None
        if not v.is_finite() or v <= 0:
            raise ValueError("CPI index must be finite and positive")
        values.append({"observed_for": key, "index_previous_month_100": str(v)})
    if not values:
        raise ValueError("no CPI observations")
    values.sort(key=lambda row: row["observed_for"])
    missing = []
    for earlier, later in zip(values, values[1:]):
        prior = date.fromisoformat(earlier["observed_for"])
        next_month = (prior.year * 12 + prior.month)
        target = date.fromisoformat(later["observed_for"])
        actual = target.year * 12 + target.month - 1
        if actual != next_month:
            missing.append({"after": earlier["observed_for"],
                            "before": later["observed_for"],
                            "missing_months": actual - next_month})
    return {
        "source": "GUS",
        "source_publication_url": official_publication_url,
        "normalized_export_sha256": hashlib.sha256(raw).hexdigest(),
        "official_raw_source_sha256": None,
        "snapshot_published_on": snapshot.isoformat(),
        "retrieved_at": collected.isoformat(),
        "source_basis": "PREVIOUS_MONTH_100",
        "input_kind": "HUMAN_MAPPED_NORMALIZED_CSV_NOT_OFFICIAL_RAW",
        "source_reuse_verification": "REQUIRES_PROVENANCE_AND_ATTRIBUTION_CHECK",
        "historical_vintage_verified": False,
        "original_release_dates_verified": False,
        "status": "INSUFFICIENT_DATA",
        "backtest": "NOT_RUN",
        "paper_events_created": 0,
        "count": len(values),
        "missing_ranges": missing,
        "observations": values,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("normalized_csv", type=Path)
    parser.add_argument("--official-publication-url", required=True)
    parser.add_argument("--snapshot-published-on", required=True)
    args = parser.parse_args()
    print(json.dumps(normalize(
        args.normalized_csv.read_bytes(),
        official_publication_url=args.official_publication_url,
        snapshot_published_on=args.snapshot_published_on,
        retrieved_at=datetime.now(timezone.utc)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
