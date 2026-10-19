"""Read-only verification of allowlisted official EIA market reference tables.

This file has no database imports, credentials, write path or trading interface.
The optional local CSV is read into memory; only aggregate/date-level
diagnostics are printed. No source HTML or reference prices are exported.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

from src.isl_v2.eia_sources import (
    SOURCES, Snapshot, SourceFormatError, parse_snapshot,
)

MAX_RESPONSE_BYTES = 8_000_000
MAX_LOCAL_CSV_BYTES = 1_000_000
MAX_LOCAL_CSV_ROWS = 15_000


def fetch_official(source: str, at: datetime, *, max_age_days: int = 420,
                   opener=urlopen) -> Snapshot:
    """HTTPS-only official EIA fetch; exact final URL and media-type checks."""
    if source not in SOURCES:
        raise SourceFormatError("Source is not allowlisted")
    if not 1 <= max_age_days <= 1500:
        raise ValueError("Invalid allowed date-window size")
    url = SOURCES[source][2]
    request = Request(url, headers={
        "Accept": "text/html",
        "User-Agent": "ISL-Educational-ReadOnly-Validation/1.0",
    })
    with opener(request, timeout=30) as response:
        if response.geturl() != url:
            raise SourceFormatError("Official EIA request redirected")
        if "text/html" not in response.headers.get("Content-Type", "").lower():
            raise SourceFormatError("Official EIA response is not HTML")
        data = response.read(MAX_RESPONSE_BYTES + 1)
    return parse_snapshot(source, data, at, max_age_days=max_age_days)


def read_local_reference_with_digest(
    path: Path, instrument: str,
) -> tuple[dict[date, Decimal], str]:
    """Parse approved local reference and hash the SAME bounded input bytes.

    Never emit the CSV body, paths or quote values. This is an input integrity
    fingerprint, not a certificate of the original publication vintage.
    """
    with path.open("rb") as source:
        data = source.read(MAX_LOCAL_CSV_BYTES + 1)
    if len(data) > MAX_LOCAL_CSV_BYTES:
        raise ValueError("Reference CSV too large")
    try:
        contents = data.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("Invalid reference CSV encoding") from exc
    observed: dict[date, Decimal] = {}
    with io.StringIO(contents, newline="") as handle:
        reader = csv.DictReader(handle)
        if (reader.fieldnames is None
                or set(reader.fieldnames) != {
                    "instrument_code", "observed_for", "close_price",
                } or len(reader.fieldnames) != 3):
            raise ValueError("Reference CSV schema must contain exactly three approved fields")
        for count, row in enumerate(reader, 1):
            if count > MAX_LOCAL_CSV_ROWS:
                raise ValueError("Reference CSV exceeds allowed rows")
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Malformed CSV row column count")
            if row.get("instrument_code") != instrument:
                raise ValueError("Reference instrument differs from EIA source")
            try:
                day = date.fromisoformat(row["observed_for"])
                price = Decimal(row["close_price"])
            except (TypeError, ValueError, InvalidOperation, KeyError):
                raise ValueError("Malformed reference date or price") from None
            if day.isoformat() != row["observed_for"]:
                raise ValueError("Reference date must be canonical ISO")
            if day in observed or not price.is_finite() or price <= 0:
                raise ValueError("Duplicate, nonfinite or nonpositive reference")
            observed[day] = price
    return observed, hashlib.sha256(data).hexdigest()


def read_local_reference(path: Path, instrument: str) -> dict[date, Decimal]:
    """Backward-compatible three-field reference reader, strictly read-only."""
    return read_local_reference_with_digest(path, instrument)[0]

def compare_dates_prices(
    snapshot: Snapshot, reference: dict[date, Decimal],
) -> dict:
    """Exact Decimal equality on *matched* official dates; no invented quotes."""
    official = {quote.observed_on: quote.price for quote in snapshot.observations}
    if len(official) != len(snapshot.observations) or not official:
        raise ValueError("Official source has duplicate/empty observations")
    lower, upper = min(official), max(official)
    in_window = {day: price for day, price in reference.items()
                 if lower <= day <= upper}
    shared = sorted(official.keys() & in_window.keys())
    missing = sorted(official.keys() - in_window.keys())
    extra = sorted(in_window.keys() - official.keys())
    mismatch = [day for day in shared if official[day] != in_window[day]]
    return {
        "status": "READ_ONLY_REFERENCE_COVERAGE_DIAGNOSTIC",
        "source_release_day": snapshot.release_day.isoformat(),
        "source_retrieved_at": snapshot.downloaded_at.isoformat(),
        "original_source_response_sha256": snapshot.sha256_hex,
        "source_url": snapshot.url,
        "instrument_code": snapshot.instrument_code,
        "window_first_date": lower.isoformat(),
        "window_last_date": upper.isoformat(),
        "source_observations": len(official),
        "reference_observations_total": len(reference),
        "reference_observations_in_window": len(in_window),
        "reference_observations_outside_window": len(reference) - len(in_window),
        "matching_dates_and_values": len(shared) - len(mismatch),
        "source_missing_from_reference": len(missing),
        "reference_dates_absent_from_source": len(extra),
        "price_mismatches": len(mismatch),
        "missing_date_keys": [day.isoformat() for day in missing],
        "mismatched_date_keys": [day.isoformat() for day in mismatch],
        "extra_date_keys": [day.isoformat() for day in extra],
        "historical_publication_vintages_verified": False,
        "source_vintage": "UNVERIFIED_HISTORICAL_PUBLICATION",
        "source_snapshot_not_historical_point_in_time": True,
        "db_reads": 0,
        "db_writes": 0,
        "real_orders": 0,
        "allocation_changes": 0,
        "schedule_enabled": False,
    }


def source_summary(snapshot: Snapshot) -> dict:
    """No raw prices or downloaded document contents in standard output."""
    first, last = snapshot.observations[0], snapshot.observations[-1]
    return {
        "status": "EIA_OFFICIAL_SOURCE_VALIDATED_READ_ONLY",
        "instrument_code": snapshot.instrument_code,
        "source_code": snapshot.source_code,
        "source_url": snapshot.url,
        "source_release_day": snapshot.release_day.isoformat(),
        "source_retrieved_at": snapshot.downloaded_at.isoformat(),
        "original_source_response_sha256": snapshot.sha256_hex,
        "first_observed": first.observed_on.isoformat(),
        "last_observed": last.observed_on.isoformat(),
        "validated_observations": len(snapshot.observations),
        "historical_publication_vintages_verified": False,
        "db_reads": 0,
        "db_writes": 0,
        "real_orders": 0,
        "allocation_changes": 0,
        "schedule_enabled": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Official EIA research-only validator: NO database connection")
    parser.add_argument("--source", choices=sorted(SOURCES), required=True)
    parser.add_argument("--max-age-days", type=int, default=420)
    parser.add_argument("--reference-csv", type=Path, default=None,
                        help="Optional LOCAL 3-column source-specific reference, never uploaded")
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.max_age_days <= 1500:
            raise ValueError("Invalid date window")
        # Fail on bad local input before initiating network access.
        reference = None
        if args.reference_csv is not None:
            code = SOURCES[args.source][0]
            reference = read_local_reference(args.reference_csv, code)
        snapshot = fetch_official(
            args.source, datetime.now(timezone.utc),
            max_age_days=args.max_age_days,
        )
        report = (source_summary(snapshot) if reference is None
                  else compare_dates_prices(snapshot, reference))
        print(json.dumps(report, sort_keys=True))
        return 0
    except Exception as exc:
        # Source bytes, local CSV paths and credentials must never leak in logs.
        print("EIA_READ_ONLY_AUDIT_FAILED: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
