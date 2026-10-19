"""Frozen WTI EIA-vs-local-history coverage receipt; read-only educational QA.

No PostgreSQL, DSN, secrets, ingestion, publishing, orders, or portfolio access.
The operator provides a locally held, permission-reviewed PUBLIC REFERENCE CSV.
Dates and EIA response SHA identify a *current* official snapshot, not proof
of when any historical observation first became publicly available.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import sys

from scripts.eia_readonly_audit import (
    compare_dates_prices, fetch_official, read_local_reference_with_digest,
)
from src.isl_v2.eia_sources import SOURCES, Snapshot

EXACT_SHA256 = re.compile(r"[a-f0-9]{64}\Z")


def review_gap(
    source_snapshot: Snapshot, reference: dict[date, Decimal], *,
    window_first: date, window_last: date, reference_cutoff: date,
    expected_release: date, expected_missing: int,
    reference_sha256: str, expected_source_sha256: str | None = None,
) -> dict:
    """Validate a predeclared WTI gap, never infer a trading recommendation."""
    if (source_snapshot.instrument_code != SOURCES["wti"][0]
            or source_snapshot.source_code != SOURCES["wti"][1]
            or source_snapshot.url != SOURCES["wti"][2]):
        raise ValueError("This review accepts only official daily WTI")
    if (source_snapshot.downloaded_at.tzinfo is None
            or source_snapshot.downloaded_at.utcoffset() is None):
        raise ValueError("Source retrieval time must be timezone-aware")
    if source_snapshot.release_day != expected_release:
        raise ValueError("EIA release differs from frozen review")
    if (expected_release > source_snapshot.downloaded_at.astimezone(timezone.utc).date()
            or window_last >= expected_release):
        raise ValueError("Source chronology is inconsistent")
    if not (window_first < reference_cutoff < window_last):
        raise ValueError("Invalid ordered review dates")
    if type(expected_missing) is not int or expected_missing < 1:
        raise ValueError("Expected source-only observations must be positive")
    if (not isinstance(reference_sha256, str)
            or not EXACT_SHA256.fullmatch(reference_sha256)
            or not isinstance(source_snapshot.sha256_hex, str)
            or not EXACT_SHA256.fullmatch(source_snapshot.sha256_hex)):
        raise ValueError("Missing or invalid source/reference fingerprints")
    if (expected_source_sha256 is not None
            and expected_source_sha256 != source_snapshot.sha256_hex):
        raise ValueError("Official EIA source content no longer matches frozen hash")

    official = tuple(s for s in source_snapshot.observations
                     if window_first <= s.observed_on <= window_last)
    if (not official or official[0].observed_on != window_first
            or official[-1].observed_on != window_last
            or len({s.observed_on for s in official}) != len(official)):
        raise ValueError("Official daily series does not cover the frozen window")
    selected_reference = {day: price for day, price in reference.items()
                          if window_first <= day <= window_last}
    if (not selected_reference or min(selected_reference) != window_first
            or max(selected_reference) != reference_cutoff
            or any(day > reference_cutoff for day in selected_reference)):
        raise ValueError("Local reference does not end at the reviewed cutoff")
    # The SHA below still authenticates the ORIGINAL FULL HTML response, not
    # a re-serialized or filtered table. Only the research window is sliced.
    selected_snapshot = replace(
        source_snapshot, observations=official, raw_count=len(official),
    )
    comparison = compare_dates_prices(selected_snapshot, selected_reference)
    official_dates = {s.observed_on for s in official}
    source_only_dates = sorted(official_dates - selected_reference.keys())
    if (comparison["price_mismatches"] != 0
            or comparison["reference_dates_absent_from_source"] != 0
            or comparison["source_missing_from_reference"] != expected_missing
            or len(source_only_dates) != expected_missing
            or any(day <= reference_cutoff for day in source_only_dates)
            or comparison["matching_dates_and_values"] != len(selected_reference)):
        raise ValueError("Frozen WTI coverage and price integrity review failed")
    return {
        "status": "WTI_EIA_GAP_REVIEW_PASSED_READ_ONLY",
        "source_url": source_snapshot.url,
        "source_code": source_snapshot.source_code,
        "source_release_day_current_snapshot": source_snapshot.release_day.isoformat(),
        "source_retrieved_at_actual": source_snapshot.downloaded_at.isoformat(),
        "source_original_html_sha256": source_snapshot.sha256_hex,
        "operator_supplied_local_reference_csv_sha256": reference_sha256,
        "reference_csv_source_provenance_verified": False,
        "current_source_not_original_historical_vintage": True,
        "source_vintage": "UNVERIFIED_HISTORICAL_PUBLICATION",
        "frozen_first_observed_for": window_first.isoformat(),
        "frozen_last_observed_for": window_last.isoformat(),
        "frozen_last_stored_observed_for": reference_cutoff.isoformat(),
        "official_observations_in_window": len(official),
        "matched_dates_and_prices": comparison["matching_dates_and_values"],
        "missing_source_dates_after_cutoff": comparison["source_missing_from_reference"],
        "source_only_observed_for_dates": comparison["missing_date_keys"],
        "source_value_mismatches": comparison["price_mismatches"],
        "locally_stored_dates_not_at_eia": comparison["reference_dates_absent_from_source"],
        "independent_point_in_time_market_data_certified": False,
        "backfill_authorized": False,
        "database_connections": 0,
        "database_writes": 0,
        "real_orders": 0,
        "portfolio_allocations_changed": 0,
        "schedule_enabled": False,
    }


def _date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Expected YYYY-MM-DD review date") from exc
    if parsed.isoformat() != value:
        raise ValueError("Noncanonical review date")
    return parsed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Frozen WTI source/reference QA, read-only; no database import"
    )
    ap.add_argument("--reference-csv", required=True, type=Path)
    ap.add_argument("--first-observed-for", required=True, type=_date)
    ap.add_argument("--last-observed-for", required=True, type=_date)
    ap.add_argument("--last-stored-observed-for", required=True, type=_date)
    ap.add_argument("--expected-source-release", required=True, type=_date)
    ap.add_argument("--expected-missing", required=True, type=int)
    ap.add_argument("--expected-source-sha256", default=None)
    ap.add_argument("--max-age-days", default=1100, type=int)
    args = ap.parse_args(argv)
    try:
        if not 1 <= args.max_age_days <= 1500:
            raise ValueError("Invalid official observation window limit")
        # All local checks occur BEFORE the external public HTTPS request.
        reference, local_hash = read_local_reference_with_digest(
            args.reference_csv, SOURCES["wti"][0])
        # This SHA-256 belongs to the exact SAME bytes parsed above.
        snapshot = fetch_official(
            "wti", datetime.now(timezone.utc), max_age_days=args.max_age_days
        )
        receipt = review_gap(
            snapshot, reference, window_first=args.first_observed_for,
            window_last=args.last_observed_for,
            reference_cutoff=args.last_stored_observed_for,
            expected_release=args.expected_source_release,
            expected_missing=args.expected_missing,
            reference_sha256=local_hash,
            expected_source_sha256=args.expected_source_sha256,
        )
        # Prints only aggregated counts, date keys and hashes: never raw
        # price quotes, input CSV content, path, login, secret or DSN.
        print(json.dumps(receipt, sort_keys=True, allow_nan=False))
        return 0
    except Exception as exc:
        print("WTI_COVERAGE_REVIEW_FAILED: " + type(exc).__name__,
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
