"""Post-backfill official EIA WTI versus Neon STAGING reconciliation, READ ONLY.

Archives the prior 660+35 frozen-gap receipt without changing it.
No broker integrations, privileged database readers, public raw quote exports,
import/write capabilities, source-PIT certification or scheduling.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

from scripts.eia_readonly_audit import (
    compare_dates_prices, fetch_official, read_local_reference_with_digest,
)
from scripts.eia_wti_staging_receipt import staging_reference_csv
from scripts.legacy_history_bridge import fetch_staging_history
from src.isl_v2.eia_sources import SOURCES, Snapshot

FIRST = date(2024, 1, 2)
LAST = date(2026, 10, 14)
EXPECTED_RELEASE = date(2026, 10, 15)
ORIGINAL_LAST = date(2026, 8, 25)
IMPORT_FIRST = date(2026, 8, 26)
IMPORT_DAY = date(2026, 10, 19)
EXPECTED_ORIGINAL_ROWS = 660
EXPECTED_NEW_ROWS = 35
EXPECTED_COMPLETE_ROWS = EXPECTED_ORIGINAL_ROWS + EXPECTED_NEW_ROWS
# Obtained independently using SHA256 of SQL date||','||numeric::text rows
# sorted by observed_for, joined with a single newline and NO final newline.
ORIGINAL_660_SHA256 = "2014f2ca99491cae91eafe3807d87300305ff201f82e24793aec21b2839862f8"
HASH_PATTERN = re.compile(r"[a-f0-9]{64}\Z")
INSTRUMENT = SOURCES["wti"][0]


def verify_staging_chronology(snapshot: dict, as_of: str) -> dict:
    """Independently validate pre/post-import historical timestamps and slice.

    These checks prove the insert is not backdated, NOT original EIA publication.
    The old 660-row content hash is locked to a previous independent SQL receipt.
    """
    read_at = datetime.fromisoformat(as_of)
    if read_at.tzinfo is None or read_at.utcoffset() is None:
        raise ValueError("Snapshot timestamp is not timezone aware")
    old, new = [], []
    for rec in snapshot["records"]:
        if rec["instrument_code"] != INSTRUMENT:
            continue
        if rec["interval_code"] != "1d" or rec["return_basis"] != "PRICE_ONLY":
            raise ValueError("Unexpected WTI observation reference basis")
        observed = datetime.fromisoformat(rec["observed_for"])
        ingested = datetime.fromisoformat(rec["ingested_at"])
        if any(x.tzinfo is None or x.utcoffset() != timedelta(0)
               for x in (observed, ingested)):
            raise ValueError("WTI timestamp must be UTC")
        if (observed.time() != time.min or ingested < observed
                or ingested > read_at):
            raise ValueError("WTI reference chronology invalid")
        key = observed.date()
        if FIRST <= key <= ORIGINAL_LAST:
            if ingested.date() >= IMPORT_DAY:
                raise ValueError("Original WTI reference was replaced after freeze")
            old.append((key, rec["close_price"]))
        elif IMPORT_FIRST <= key <= LAST:
            if ingested.date() != IMPORT_DAY:
                raise ValueError("Backfilled WTI import date changed or backdated")
            new.append((key, rec["close_price"]))
        else:
            raise ValueError("WTI observed date outside frozen post-import window")

    if (len(old) != EXPECTED_ORIGINAL_ROWS
            or len(new) != EXPECTED_NEW_ROWS
            or len({d for d, _ in old+new}) != EXPECTED_COMPLETE_ROWS
            or not old or not new
            or min(d for d, _ in old) != FIRST
            or max(d for d, _ in old) != ORIGINAL_LAST
            or min(d for d, _ in new) != IMPORT_FIRST
            or max(d for d, _ in new) != LAST):
        raise ValueError("WTI staging reference chronology or coverage drifted")
    legacy_hash = hashlib.sha256(
        "\n".join(f"{day.isoformat()},{price}" for day, price in sorted(old)).encode("utf-8")
    ).hexdigest()
    if legacy_hash != ORIGINAL_660_SHA256:
        raise ValueError("Frozen original 660-row content fingerprint differs")
    return {
        "previously_stored_rows": len(old),
        "backfilled_rows": len(new),
        "backfill_recorded_date_utc": IMPORT_DAY.isoformat(),
        "unchanged_prior_660_sha256": legacy_hash,
        "source_publication_vintages_verified": False,
    }


def review_complete(source: Snapshot, reference: dict[date, Decimal], *,
                    reference_sha256: str, chronology: dict) -> dict:
    """Review one *current* EIA original-HTML snapshot against 695 stored days."""
    if (source.instrument_code, source.source_code, source.url) != SOURCES["wti"]:
        raise ValueError("Only official EIA WTI source accepted")
    if (source.downloaded_at.tzinfo is None or
            source.downloaded_at.utcoffset() is None or
            source.release_day != EXPECTED_RELEASE or
            source.downloaded_at.astimezone(timezone.utc).date() < EXPECTED_RELEASE):
        raise ValueError("EIA publication or retrieval chronology changed")
    if not all(isinstance(x, str) and HASH_PATTERN.fullmatch(x)
               for x in (source.sha256_hex, reference_sha256)):
        raise ValueError("Source/reference hashes must authenticate input bytes")

    official = {x.observed_on: x.price for x in source.observations
                if FIRST <= x.observed_on <= LAST}
    if (len(official) != EXPECTED_COMPLETE_ROWS
            or not official or min(official) != FIRST or max(official) != LAST
            or len(reference) != EXPECTED_COMPLETE_ROWS
            or min(reference) != FIRST or max(reference) != LAST
            or len({x.observed_on for x in source.observations
                    if FIRST <= x.observed_on <= LAST}) != len(
                        [x for x in source.observations if FIRST <= x.observed_on <= LAST])):
        raise ValueError("Frozen WTI EIA/Neon coverage or row uniqueness changed")

    # Existing comparator is Decimal-exact; reject any missing, added, or
    # mismatched calendar key (not just a matching total row count).
    from dataclasses import replace
    selected = replace(
        source,
        observations=tuple(x for x in source.observations
                           if FIRST <= x.observed_on <= LAST),
        raw_count=EXPECTED_COMPLETE_ROWS,
    )
    compared = compare_dates_prices(selected, reference)
    if (compared["matching_dates_and_values"] != EXPECTED_COMPLETE_ROWS
            or compared["source_missing_from_reference"] != 0
            or compared["reference_dates_absent_from_source"] != 0
            or compared["price_mismatches"] != 0
            or compared["reference_observations_outside_window"] != 0):
        raise ValueError("WTI post-import date and quote integrity failed")

    # This is the *new/current* HTML snapshot, not proof of the original
    # publication date of each old individual observed price.
    day_after_release = datetime.combine(
        EXPECTED_RELEASE + timedelta(days=1), time.min, tzinfo=timezone.utc)
    available_not_before = max(source.downloaded_at.astimezone(timezone.utc),
                               day_after_release)
    return {
        "status": "WTI_POSTIMPORT_EIA_STAGING_695_MATCH_READ_ONLY",
        "source_url": source.url,
        "source_code": source.source_code,
        "source_release_day_of_current_page": source.release_day.isoformat(),
        "publication_precision": "DAY_CURRENT_SNAPSHOT_ONLY",
        "source_retrieved_at_actual": source.downloaded_at.isoformat(),
        "current_source_available_not_before_utc": available_not_before.isoformat(),
        "source_original_html_sha256": source.sha256_hex,
        "staging_reference_csv_sha256": reference_sha256,
        "data_window_first": FIRST.isoformat(),
        "data_window_last": LAST.isoformat(),
        "official_observations_in_window": EXPECTED_COMPLETE_ROWS,
        "staging_observations_in_window": EXPECTED_COMPLETE_ROWS,
        "matching_dates_and_prices": compared["matching_dates_and_values"],
        "source_missing_from_reference": 0,
        "staging_dates_absent_from_official_source": 0,
        "price_mismatches": 0,
        **chronology,
        "source_vintage": "UNVERIFIED_HISTORICAL_PUBLICATION",
        "historical_retrieval_at_for_individual_prices_verified": False,
        "versioned_market_documents_created": 0,
        "versioned_market_observations_created": 0,
        "independent_point_in_time_market_data_certified": False,
        "reference_reader_acl_verified": True,
        "database_connections": 1,
        "database_reads": 1,
        "database_writes": 0,
        "real_orders": 0,
        "portfolio_allocations_changed": 0,
        "schedule_enabled": False,
    }


def audit(dsn: str) -> dict:
    """An authorized SELECT-only staging bridge plus public EIA HTTPS fetch."""
    snapshot, manifest = fetch_staging_history(dsn)
    if (manifest["series_counts"].get(INSTRUMENT) != EXPECTED_COMPLETE_ROWS
            or manifest["source_vintage"] != "UNVERIFIED_HISTORICAL_PUBLICATION"
            or manifest["database_writes"] != 0):
        raise ValueError("Dedicated reader reference manifest drifted")
    # Validate the historical insertion timestamps BEFORE external HTTPS.
    chronology = verify_staging_chronology(snapshot, manifest["as_of"])
    csv_bytes = staging_reference_csv(
        snapshot, first=FIRST, stored_last=LAST, expected_rows=EXPECTED_COMPLETE_ROWS)

    with TemporaryDirectory(prefix="isl-postimport-readonly-") as folder:
        path = Path(folder) / "ephemeral-public-wti.csv"
        with os.fdopen(os.open(path, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600),
                       "wb") as handle:
            handle.write(csv_bytes)
        del csv_bytes
        reference, reference_hash = read_local_reference_with_digest(path, INSTRUMENT)
        source = fetch_official("wti", datetime.now(timezone.utc), max_age_days=1100)
        return review_complete(
            source, reference, reference_sha256=reference_hash,
            chronology=chronology,
        )


def main() -> int:
    try:
        print(json.dumps(audit(os.getenv("NEON_HISTORICAL_READ_DATABASE_URL", "")),
                         sort_keys=True, allow_nan=False))
        return 0
    except Exception as exc:
        # Do NOT print raw psycopg exception (may contain host or DSN).
        print("WTI_POSTIMPORT_RECEIPT_FAILED: " + type(exc).__name__,
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
