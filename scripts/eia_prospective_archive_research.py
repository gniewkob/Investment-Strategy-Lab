"""Offline prospective EIA version comparison from independently verified RAW archives.

Zero network, no database, no output of source HTML or numerical price levels,
no trading or paper allocation changes. First acquisition is a dated BASELINE;
subsequent acquisitions can expose newly seen dates and revisions *relative to
that baseline*, but cannot establish original historical publication vintages.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import sys

from src.isl_v2.eia_sources import SOURCES, SourceFormatError
from src.isl_v2.eia_versioned_ingest import MAX_SOURCE_BYTES, prepare
from src.isl_v2.eia_raw_archive import (
    _root_fd, _subdir, _read_exact, verify_receipt, UTC_STAMP,
)
from src.isl_v2.eia_semantic_evidence import semantic_evidence

RECEIPT_NAME = re.compile(r"(?P<stamp>\d{8}T\d{6}\.\d{6}Z)_(?P<sha>[a-f0-9]{64})\.json\Z")
MAX_RECEIPTS_PER_SOURCE = 128
MAX_RECEIPT_BYTES = 16_384


def _read_records(root: str, slug: str):
    if slug not in SOURCES:
        raise SourceFormatError("Source is not in EIA allowlist")
    source_code = SOURCES[slug][1]
    fd = _root_fd(root)
    try:
        objects = _subdir(fd, "objects", create=False)
        try:
            receipts = _subdir(fd, "receipts", create=False)
            try:
                folder = _subdir(receipts, source_code, create=False)
                try:
                    names = os.listdir(folder)
                    # A private root is not an invitation to scan unbounded files.
                    if (not 1 <= len(names) <= MAX_RECEIPTS_PER_SOURCE or
                            any(not RECEIPT_NAME.fullmatch(n) for n in names)):
                        raise SourceFormatError("Archive receipts missing or not allowlisted")
                    records = []
                    for name in sorted(names):
                        match = RECEIPT_NAME.fullmatch(name)
                        assert match is not None
                        manifest_raw = _read_exact(folder, name, MAX_RECEIPT_BYTES)
                        try:
                            manifest = json.loads(manifest_raw.decode("utf-8"))
                        except (ValueError, UnicodeDecodeError) as exc:
                            raise SourceFormatError("Archive manifest JSON invalid") from exc
                        if not isinstance(manifest, dict):
                            raise SourceFormatError("Archive manifest must be an object")
                        digest = match.group("sha")
                        try:
                            at = datetime.fromisoformat(manifest["retrieved_at"])
                        except (KeyError, TypeError, ValueError) as exc:
                            raise SourceFormatError("Manifest retrieval time invalid") from exc
                        if (at.tzinfo is None or at.utcoffset() is None or
                                at.astimezone(timezone.utc).strftime(UTC_STAMP) != match.group("stamp") or
                                manifest.get("source_code") != source_code or
                                manifest.get("original_html_sha256") != digest):
                            raise SourceFormatError("Manifest source or acquisition identity mismatch")
                        # This routine independently validates the saved bytes and
                        # the EXACT manifest, including semantic evidence.
                        proof = verify_receipt(root, source_code, digest, at)
                        raw = _read_exact(objects, digest + ".html", MAX_SOURCE_BYTES)
                        if hashlib.sha256(raw).hexdigest() != digest:
                            raise SourceFormatError("Archive HTML bytes changed after proof")
                        age_days = manifest.get("max_age_days")
                        if type(age_days) is not int or not 1 <= age_days <= 1500:
                            raise SourceFormatError("Archive parser window invalid")
                        plan = prepare(slug, raw, at, max_age_days=age_days)
                        sem = semantic_evidence(plan.snapshot)
                        if (sem["semantic_observations_sha256"] !=
                                manifest["semantic_observations_sha256"] or
                                proof["semantic_observations_sha256"] !=
                                sem["semantic_observations_sha256"]):
                            raise SourceFormatError("Archive semantic provenance changed")
                        records.append((plan, manifest))
                finally:
                    os.close(folder)
            finally:
                os.close(receipts)
        finally:
            os.close(objects)
    finally:
        os.close(fd)
    # Refuse multiple different documents for the exact same acquired-at:
    # distinct byte hashes cannot both be asserted as the sole acquisition.
    records.sort(key=lambda p: p[0].snapshot.downloaded_at)
    times = [p[0].snapshot.downloaded_at for p in records]
    if len(set(times)) != len(times):
        raise SourceFormatError("Conflicting EIA source capture timestamps")
    return records


def _compare(prior, later) -> dict:
    earlier = {p.observed_on: p.price for p in prior.snapshot.observations}
    current = {p.observed_on: p.price for p in later.snapshot.observations}
    same = earlier.keys() & current.keys()
    revised = sum(earlier[date] != current[date] for date in same)
    newer = current.keys() - earlier.keys()
    removed = earlier.keys() - current.keys()
    return {
        "prior_retrieved_at": prior.snapshot.downloaded_at.isoformat(),
        "current_retrieved_at": later.snapshot.downloaded_at.isoformat(),
        "overlapping_observed_dates": len(same),
        "unchanged_overlapping_prices": len(same) - revised,
        "revised_overlapping_prices": revised,
        "newly_seen_observed_dates": len(newer),
        "no_longer_in_current_window": len(removed),
        "raw_html_hash_changed": prior.source_bytes_sha256 != later.source_bytes_sha256,
        "semantic_hash_changed": semantic_evidence(prior.snapshot)[
            "semantic_observations_sha256"] != semantic_evidence(later.snapshot)[
            "semantic_observations_sha256"],
        "historical_original_release_dates_verified": False,
        "price_change_interpretation": (
            "SOURCE_REVISION_REVIEW_REQUIRED" if revised
            else "NO_PRICE_REVISIONS_ON_OVERLAPPING_OBSERVED_DATES"
        ),
    }


def inspect_archive(root: str) -> dict:
    """Summarize true archived vintages, not hypothetical past availability."""
    out = []
    revised_count = 0
    for slug in ("wti", "brent", "henry_hub"):
        items = _read_records(root, slug)
        current, manifest = items[-1]
        snapshot = current.snapshot
        comparisons = []
        for (earlier, _), (later, _) in zip(items, items[1:]):
            delta = _compare(earlier, later)
            revised_count += delta["revised_overlapping_prices"]
            comparisons.append(delta)
        out.append({
            "instrument_code": snapshot.instrument_code,
            "source_code": snapshot.source_code,
            "captured_vintages": len(items),
            "first_capture_at": items[0][0].snapshot.downloaded_at.isoformat(),
            "latest_capture_at": snapshot.downloaded_at.isoformat(),
            "latest_current_release_day": snapshot.release_day.isoformat(),
            "latest_available_not_before": current.available_at.isoformat(),
            "latest_raw_html_sha256": current.source_bytes_sha256,
            "latest_semantic_sha256": semantic_evidence(snapshot)["semantic_observations_sha256"],
            "latest_observation_count": len(snapshot.observations),
            "latest_first_observed_date": snapshot.observations[0].observed_on.isoformat(),
            "latest_last_observed_date": snapshot.observations[-1].observed_on.isoformat(),
            "comparisons": comparisons,
            "research_readiness": (
                "PROSPECTIVE_REVISION_REVIEW_ONLY" if any(
                    c["revised_overlapping_prices"] > 0 for c in comparisons)
                else "PROSPECTIVE_VINTAGE_COMPARISON_DESCRIPTIVE_ONLY"
                if comparisons else "FIRST_SOURCE_CAPTURE_BASELINE_ONLY"
            ),
        })
    return {
        "status": "EIA_PROSPECTIVE_ARCHIVE_DESCRIPTIVE_AUDIT",
        "archive_sources_verified": len(out),
        "source_series": out,
        "total_overlapping_price_revisions_since_captured_baseline": revised_count,
        "original_historical_publication_vintages_verified": False,
        "historical_point_in_time_backtest_certified": False,
        "predictive_advantage_established": False,
        "investable_total_return_data_verified": False,
        "decision": "RESEARCH_ONLY_HOLD_NO_CHANGE",
        "virtual_model_allocations_changed": 0,
        "paper_fills": 0,
        "real_orders": 0,
        "database_connections": 0,
        "database_writes": 0,
        "external_http_requests": 0,
        "file_creations": 0,
        "schedule_enabled": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Local archived EIA vintage comparison — READ ONLY, NO TRADES")
    parser.add_argument("--archive-root", required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect_archive(args.archive_root)
        print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
        return 0
    except Exception as exc:
        # Never print original HTML, raw values, host, paths or credentials.
        print("EIA_PROSPECTIVE_ARCHIVE_AUDIT_FAILED: " + type(exc).__name__,
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
