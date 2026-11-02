"""Independent, strictly read-only M1 G5 recovery-window acceptance.

This is a NEW acceptance attempt, not retroactive approval of G3-anchored G5.
Start boundary is fixed after the documented 122.4s collector gap.
The original owner-private G3 receipt and entire append-only sample ledger remain
unchanged. No service control, network, wallets, trades, or private-path output.

Requires pinned PR #90 assessor, which remains a separate unmerged change.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time

from scripts import m1_g4_g5_postcutover_readonly as original
from scripts import m1_readonly_evidence as evidence
from scripts import unattended_acceptance as acceptance

MODE = "M1_G5_RECOVERY_ACCEPTANCE_READONLY_V1"
RECOVERY_START_ISO = "2026-11-01T18:18:51Z"
RECOVERY_START = datetime.fromisoformat(
    RECOVERY_START_ISO.replace("Z", "+00:00")).timestamp()
MIN_SECONDS = 86_400
MAX_INCIDENT_GROUPS = 16
KNOWN_STATUSES = frozenset((
    "OBSERVATION_OK", "PARTIAL", "INVALID", "STALE", "UNAVAILABLE", "UNKNOWN"
))
KNOWN_SOURCE_STATUSES = frozenset((
    "OK", "PARTIAL", "INVALID", "STALE", "UNAVAILABLE", "UNKNOWN"
))


def require(condition):
    if not condition:
        raise ValueError("M1_G5_RECOVERY_READONLY_REJECTED")


def utc(value):
    require(type(value) in (int, float) and math.isfinite(value))
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace(
        "+00:00", "Z")


def safe_status(value, allowed):
    return value if type(value) is str and value in allowed else "UNKNOWN"


def incident_analysis(rows, g3_time):
    """Summarize failures before recovery, without exposing private data."""
    earlier = [r for r in rows
               if g3_time < r["observed_at"] <= RECOVERY_START]
    status_counts = Counter(safe_status(r.get("status"), KNOWN_STATUSES)
                            for r in earlier)
    failed_sources = Counter()
    for r in earlier:
        provided = r.get("sources")
        for name in acceptance.SOURCE_NAMES:
            value = (provided.get(name) if type(provided) is dict else None)
            state = safe_status(value, KNOWN_SOURCE_STATUSES)
            if state != "OK":
                failed_sources[f"{name}:{state}"] += 1

    # Group by *distinct natural checkpoint*, not by 60-second polls.
    groups = {}
    for row in earlier:
        if row.get("status") != "PARTIAL":
            continue
        cp = row.get("checkpoint_at")
        valid = (type(cp) in (float, int) and math.isfinite(cp)
                 and cp > g3_time and cp <= row["observed_at"] + 5)
        key = cp if valid else None
        if key not in groups:
            groups[key] = {
                "first": row["observed_at"],
                "last": row["observed_at"],
                "samples": 0,
                "sources": Counter(),
            }
        group = groups[key]
        group["last"] = row["observed_at"]
        group["samples"] += 1
        provided = row.get("sources")
        for name in acceptance.SOURCE_NAMES:
            value = (provided.get(name) if type(provided) is dict else None)
            state = safe_status(value, KNOWN_SOURCE_STATUSES)
            if state != "OK":
                group["sources"][f"{name}:{state}"] += 1

    timeline = [{
        "checkpoint_utc": utc(cp) if cp is not None else "UNVERIFIED",
        "first_sample_utc": utc(item["first"]),
        "last_sample_utc": utc(item["last"]),
        "partial_samples": item["samples"],
        "source_failure_counts": dict(sorted(item["sources"].items())),
    } for cp, item in sorted(
        groups.items(), key=lambda pair: pair[1]["first"])][:MAX_INCIDENT_GROUPS]

    gaps = []
    for prior, current in zip(earlier, earlier[1:]):
        duration = current["observed_at"] - prior["observed_at"]
        if duration > 120:
            gaps.append({
                "start_utc": utc(prior["observed_at"]),
                "end_utc": utc(current["observed_at"]),
                "seconds": round(duration, 3)
            })
    return {
        "period": "AFTER_G3_THROUGH_FIXED_RECOVERY_BOUNDARY",
        "samples": len(earlier),
        "status_counts": dict(sorted(status_counts.items())),
        "unhealthy_samples": sum(
            not original.safe_healthy(r) for r in earlier),
        "coverage_failed_samples": sum(
            r.get("coverage_ok") is not True for r in earlier),
        "watchdog_mismatch_samples": sum(
            r.get("watchdog_matches") is not True for r in earlier),
        "source_failure_counts": dict(sorted(failed_sources.items())),
        "partial_unique_checkpoint_groups": len(groups),
        "partial_checkpoint_groups": timeline,
        "checkpoint_groups_truncated": len(groups) > MAX_INCIDENT_GROUPS,
        "poll_gaps_over_120s": len(gaps),
        "poll_gap_examples": gaps[:MAX_INCIDENT_GROUPS],
        "gap_examples_truncated": len(gaps) > MAX_INCIDENT_GROUPS,
    }


def assess(rows, g3_boundary, now):
    """Report ORIGINAL acceptance and independent RECOVERY acceptance separately.

    Do not backdate or move the fixed recovery boundary to cherry-pick health.
    Exact historical failures remain visible in ORIGINAL forever.
    """
    require(type(g3_boundary) in (int, float) and math.isfinite(g3_boundary)
            and 0 < g3_boundary < RECOVERY_START)
    require(type(now) in (int, float) and math.isfinite(now)
            and now >= RECOVERY_START - 5)
    # Both assessors validate monotonic, bounded, finite observation times.
    historic = original.evaluate(rows, g3_boundary, now)
    recovery = original.evaluate(rows, RECOVERY_START, now)
    prior = incident_analysis(rows, g3_boundary)
    return {
        "mode": MODE,
        "scope": "READ_ONLY_EXISTING_EVIDENCE_NOT_PROVIDER_ATTESTATION",
        "recovery_start_utc": RECOVERY_START_ISO,
        "recovery_start_fixed": True,
        "historical_g3_based_acceptance": {
            "g4_status": historic["g4_natural_cycles"],
            "g5_status": historic["g5_24h"],
            "g5_reasons": historic["g5_reasons"],
            "post_g3_samples": historic["post_g3_samples"],
            "preserved_not_reclassified": True,
        },
        "prior_incidents": prior,
        "recovery_window": {
            "g4_status": recovery["g4_natural_cycles"],
            "g5_status": recovery["g5_24h"],
            "reasons": recovery["g5_reasons"],
            "span_seconds": recovery["post_g3_observed_span_seconds"],
            "required_span_seconds": MIN_SECONDS,
            "natural_checkpoints": recovery["natural_checkpoints"],
            "required_natural_checkpoints": original.MIN_CHECKPOINTS,
            "post_start_samples": recovery["post_g3_samples"],
            "partial_samples": recovery["partial_samples"],
            "invalid_samples": recovery["invalid_samples"],
            "unhealthy_samples": recovery["unhealthy_samples"],
            "collector_gaps_over_120s": recovery["collector_gaps_over_120s"],
            "last_sample_age_seconds": recovery["last_sample_age_seconds"],
            "bad_checkpoint_intervals": recovery["bad_checkpoint_intervals"],
            "http429_unknown_samples": recovery["http429_unknown_samples"],
            "financial_invariant": recovery["financial_invariant"],
        },
        "g6": "BLOCKED_PENDING_FINAL_SIGNOFF",
        "financial_operations_performed_by_assessor": 0,
        "historical_ledger_modified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--g3-receipt", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        cutover = original.trusted_cutover_time(
            args.g3_receipt, os.getuid())
        ledger = original.existing_samples_path(Path.home(), os.getuid())
        result = assess(evidence.read_samples(ledger), cutover, time.time())
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 3 if result["recovery_window"]["g5_status"] == "REVIEW" else 0
    except Exception:
        # Never print paths, configuration, ledger records, or credentials.
        print("M1_G5_RECOVERY_READONLY_REJECTED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
