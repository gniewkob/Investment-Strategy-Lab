"""Manual, frozen official EIA-versus-Neon-STAGING WTI audit.

The historical reader has SELECT on one public-reference table only.
All raw quotes stay in an ephemeral 0600 local CSV, deleted before reporting.
Outputs are aggregate evidence, not point-in-time provenance or trades.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import io
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from scripts.eia_readonly_audit import fetch_official, read_local_reference_with_digest
from scripts.eia_wti_gap_receipt import review_gap
from scripts.legacy_history_bridge import fetch_staging_history
from src.isl_v2.eia_sources import SOURCES

WINDOW_FIRST = date(2024, 1, 2)
WINDOW_LAST = date(2026, 10, 14)
STORED_LAST = date(2026, 8, 25)
EXPECTED_RELEASE = date(2026, 10, 15)
EXPECTED_STORED_ROWS = 660
EXPECTED_MISSING = 35
INSTRUMENT = SOURCES["wti"][0]


def staging_reference_csv(snapshot: dict, *,
                          first: date = WINDOW_FIRST,
                          stored_last: date = STORED_LAST,
                          expected_rows: int = EXPECTED_STORED_ROWS) -> bytes:
    """Canonical public reference CSV, in memory; no private/account tables.

    The existing read-only history bridge validates source mappings, timestamps,
    duplicate records and the dedicated least-privilege database identity.
    This function rejects any drifting WTI reference window before HTTPS.
    """
    if (snapshot.get("mode") != "RETROSPECTIVE_RESEARCH_ONLY"
            or snapshot.get("source_vintage") != "UNVERIFIED_HISTORICAL_PUBLICATION"
            or not isinstance(snapshot.get("records"), list)):
        raise ValueError("Unverified historical reference snapshot contract")
    if not (first < stored_last and expected_rows > 1):
        raise ValueError("Invalid frozen staging reference contract")
    by_date: dict[date, Decimal] = {}
    for record in snapshot["records"]:
        if record.get("instrument_code") != INSTRUMENT:
            continue
        if (record.get("interval_code") != "1d"
                or record.get("return_basis") != "PRICE_ONLY"):
            raise ValueError("Unexpected WTI reference type")
        try:
            observed = datetime.fromisoformat(record["observed_for"])
            if (observed.tzinfo is None or observed.utcoffset() is None
                    or observed.utcoffset().total_seconds() != 0):
                raise ValueError("Non-UTC reference date")
            day = observed.date()
            price = Decimal(record["close_price"])
        except (TypeError, KeyError, ValueError, InvalidOperation) as exc:
            raise ValueError("Malformed WTI staging reference row") from None
        if (not first <= day <= stored_last or day in by_date
                or not price.is_finite() or price <= 0):
            raise ValueError("WTI staging reference window or price violated")
        by_date[day] = price

    if (len(by_date) != expected_rows or not by_date
            or min(by_date) != first or max(by_date) != stored_last):
        raise ValueError("WTI staging reference coverage drifted")

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(("instrument_code", "observed_for", "close_price"))
    for day, price in sorted(by_date.items()):
        writer.writerow((INSTRUMENT, day.isoformat(), str(price)))
    return buffer.getvalue().encode("utf-8")


def audit(dsn: str) -> dict:
    """One run: verified staging SELECT, then official raw HTML HTTPS and compare.

    Uses existing readers only; no INSERT/UPDATE, privileges, ingestion or
    recurring automation. Never emits prices, credentials or source HTML.
    """
    snapshot, manifest = fetch_staging_history(dsn)
    csv_bytes = staging_reference_csv(snapshot, expected_rows=EXPECTED_STORED_ROWS)
    if (manifest["series_counts"].get(INSTRUMENT) != EXPECTED_STORED_ROWS
            or manifest["database_writes"] != 0
            or manifest["source_vintage"] != "UNVERIFIED_HISTORICAL_PUBLICATION"):
        raise ValueError("Staging read-only source manifest mismatch")

    with TemporaryDirectory(prefix="isl-wti-audit-") as directory:
        # The exact bytes audited and hashed by the already-tested CSV reader.
        # GitHub uploads only the resulting aggregate JSON, never this file.
        csv_path = Path(directory) / "public-wti-reference.csv"
        with os.fdopen(os.open(csv_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600),
                       "wb") as stream:
            stream.write(csv_bytes)
        del csv_bytes
        reference, reference_hash = read_local_reference_with_digest(csv_path, INSTRUMENT)
        official = fetch_official("wti", datetime.now(timezone.utc), max_age_days=1100)
        result = review_gap(
            official, reference,
            window_first=WINDOW_FIRST, window_last=WINDOW_LAST,
            reference_cutoff=STORED_LAST, expected_release=EXPECTED_RELEASE,
            expected_missing=EXPECTED_MISSING, reference_sha256=reference_hash,
        )

    # The reusable local-CSV-only function correctly reported zero DB accesses.
    # This wrapper DID perform a separate read-only staging database connection.
    local_hash = result.pop("operator_supplied_local_reference_csv_sha256")
    result["staging_reference_csv_sha256"] = local_hash
    result["reference_origin"] = "NEON_STAGING_LEGACY_PUBLIC_REFERENCE_READ_ONLY"
    result["historical_reader_acl_verified"] = True
    result["staging_reference_rows"] = EXPECTED_STORED_ROWS
    result["database_connections"] = 1
    result["database_reads"] = 1
    result["database_writes"] = 0
    result["reference_csv_source_provenance_verified"] = False
    result["independent_point_in_time_market_data_certified"] = False
    result["backfill_authorized"] = False
    result["real_orders"] = 0
    result["portfolio_allocations_changed"] = 0
    result["schedule_enabled"] = False
    return result


def main() -> int:
    try:
        report = audit(os.getenv("NEON_HISTORICAL_READ_DATABASE_URL", ""))
        print(json.dumps(report, sort_keys=True, allow_nan=False))
        return 0
    except Exception as exc:
        # libpq errors and filesystem exceptions can expose credentials/paths.
        print("WTI_STAGING_RECEIPT_FAILED: " + type(exc).__name__,
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
