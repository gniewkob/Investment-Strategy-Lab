"""Read-only G4/G5 assessor scoped to samples strictly after a successful G3.

No launchctl invocation, network access, credentials, financial transactions,
writes, restarts or changes to existing evidence. The receipt's private-file
mtime is a conservative completion boundary, not a signed deployment time.
This tool does not replace a separate live isolated-after G4 preflight.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import stat

from scripts import m1_predeploy_readiness as preflight
from scripts import m1_readonly_evidence as evidence
from scripts import unattended_acceptance as acceptance

CANDIDATE = "ded973833407532ca6095c50577fbdd046cd536c"
RECEIPT_STATUS = "G3_COLLECTOR_ONLY_CUTOVER_AND_G4_METADATA_PASS"
G5_SECONDS = 86_400
MIN_CHECKPOINTS = 90


def require(ok):
    if not ok:
        raise ValueError("M1_G4_G5_READONLY_REJECTED")


def trusted_cutover_time(path, uid):
    """Validate private receipt; return its stat-verified end-time boundary."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as f:
        st = os.fstat(f.fileno())
        require(stat.S_ISREG(st.st_mode) and st.st_uid == uid
                and not st.st_mode & 0o077 and 0 < st.st_size <= 8192)
        payload = f.read(8193)
        require(len(payload) == st.st_size)
        receipt = json.loads(payload)
    require(type(receipt) is dict
            and receipt.get("status") == RECEIPT_STATUS
            and receipt.get("candidate_sha") == CANDIDATE
            and receipt.get("rollback_bundle_id") == "m1-2mLN75Z6aQ"
            and type(receipt.get("financial_operations")) is int
            and receipt["financial_operations"] == 0
            and receipt.get("g5_24h_completed") is False
            and receipt.get("production_supervisor_or_watchdog_modified") is False)
    return st.st_mtime


def existing_samples_path(home, uid):
    """Discover only the deployed collector's recorded output directory."""
    definition = preflight.read_launchagent(home, preflight.LABEL_COLLECTOR, uid)
    require(definition.get("Label") == preflight.LABEL_COLLECTOR
            and definition.get("StartInterval") == 60)
    argv = definition.get("ProgramArguments")
    require(type(argv) is list and len(argv) >= 3 and argv[1] == "-I")
    options = preflight.collector_options(argv, collector_phase="isolated-after")
    require(options["--expected-commit"] ==
            "93038ca62edff39492f9b8ddb68d890e3e6e5c45")
    return Path(options["--output"]) / "samples.jsonl"


def safe_healthy(row):
    try:
        return acceptance.healthy(row) is True
    except (TypeError, KeyError, ValueError, AttributeError):
        return False


def evaluate(rows, cutover, now):
    """Evaluate fixed post-G3 window; reject pre-G3 evidence for G4/G5."""
    require(type(cutover) in (float, int) and math.isfinite(cutover)
            and type(now) in (float, int) and math.isfinite(now)
            and 0 < cutover <= now + 5)
    prior = float("-inf")
    for row in rows:
        require(type(row) is dict
                and type(row.get("observed_at")) in (int, float)
                and math.isfinite(row["observed_at"])
                and row["observed_at"] > prior)
        prior = row["observed_at"]
    post = [r for r in rows if r["observed_at"] > cutover]
    g4_reasons = []
    if not post:
        if now - cutover > 120:
            g4_reasons.append("NO_POST_G3_SAMPLES")
    else:
        if post[0]["observed_at"] - cutover > 120:
            g4_reasons.append("START_BOUNDARY_GAP")
        age = now - post[-1]["observed_at"]
        if age < -5 or age > 120:
            g4_reasons.append("STALE_OR_FUTURE_LAST_SAMPLE")

    gaps = [b["observed_at"] - a["observed_at"]
            for a, b in zip(post, post[1:])]
    interrupted = sum(g <= 0 or g > 120 for g in gaps)
    if interrupted:
        g4_reasons.append("COLLECTOR_GAPS")
    unhealthy = sum(not safe_healthy(r) for r in post)
    invalid = sum(r.get("status") == "INVALID" for r in post)
    partial = sum(r.get("status") == "PARTIAL" for r in post)
    if unhealthy:
        g4_reasons.append("UNHEALTHY_SAMPLES")
    if invalid or partial:
        g4_reasons.append("INVALID_OR_PARTIAL_SAMPLES")
    financial_ok = all(type(r.get("financial_operations")) is int
                       and r["financial_operations"] == 0 for r in post)
    if not financial_ok:
        g4_reasons.append("FINANCIAL_INVARIANT")

    natural = {}
    for row in post:
        cp = row.get("checkpoint_at")
        runtime = row.get("runtime")
        if (type(cp) in (int, float) and math.isfinite(cp)
                and cp > cutover and cp <= row["observed_at"] + 5
                and type(runtime) is dict
                and runtime.get("unique_natural_supervisor") is True):
            natural[cp] = row
    times = sorted(natural)
    cadence = [b - a for a, b in zip(times, times[1:])]
    bad_cadence = sum(not 900 <= d <= 1020 for d in cadence)
    if bad_cadence:
        g4_reasons.append("NATURAL_CADENCE_OUT_OF_RANGE")

    identities = {
        (r.get("runtime", {}).get("pid"),
         r.get("runtime", {}).get("process_start"))
        for r in post if type(r.get("runtime")) is dict
    }
    definitions = {
        tuple(r.get("runtime", {}).get("launchagent_hashes") or [])
        for r in post if type(r.get("runtime")) is dict
    }
    if post and (len(identities) != 1 or any(None in x for x in identities)):
        g4_reasons.append("SUPERVISOR_IDENTITY_CHANGE_OR_UNKNOWN")
    if post and (len(definitions) != 1 or any(not x for x in definitions)):
        g4_reasons.append("LAUNCHAGENT_CHANGE_OR_UNKNOWN")

    telemetry_unknown = sum(type(r.get("http_429_count")) is not int
                            for r in post)
    g5_reasons = list(g4_reasons)
    if telemetry_unknown:
        g5_reasons.append("HTTP429_TELEMETRY_UNKNOWN")

    g4 = ("REVIEW" if g4_reasons else
          "PASS" if len(times) >= 2 else "PENDING_NATURAL_CYCLES")
    span = post[-1]["observed_at"] - cutover if post else 0
    if g5_reasons:
        g5 = "REVIEW"
    elif span < G5_SECONDS or len(times) < 2:
        g5 = "PENDING_WINDOW"
    elif len(times) < MIN_CHECKPOINTS:
        g5 = "REVIEW"
        g5_reasons.append("INSUFFICIENT_NATURAL_CHECKPOINTS")
    else:
        g5 = "PASS"

    return {
        "mode": "M1_G4_G5_POSTCUTOVER_READONLY_V1",
        "scope": "POST_G3_LEDGER_ONLY_NOT_PROVIDER_ATTESTATION",
        "g4_natural_cycles": g4,
        "g5_24h": g5,
        "post_g3_samples": len(post),
        "natural_checkpoints": len(times),
        "last_checkpoint_interval_seconds": cadence[-1] if cadence else None,
        "bad_checkpoint_intervals": bad_cadence,
        "unhealthy_samples": unhealthy,
        "invalid_samples": invalid,
        "partial_samples": partial,
        "collector_gaps_over_120s": interrupted,
        "last_sample_age_seconds": (round(now - post[-1]["observed_at"], 1)
                                    if post else None),
        "post_g3_observed_span_seconds": round(span, 1),
        "financial_invariant": "PASS" if financial_ok else "FAIL",
        "http429_unknown_samples": telemetry_unknown,
        "g4_reasons": sorted(set(g4_reasons)),
        "g5_reasons": sorted(set(g5_reasons)),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--g3-receipt", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        cutover = trusted_cutover_time(args.g3_receipt, os.getuid())
        ledger = existing_samples_path(Path.home(), os.getuid())
        report = evaluate(evidence.read_samples(ledger), cutover,
                          datetime.now(timezone.utc).timestamp())
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
        return 0 if "REVIEW" not in (report["g4_natural_cycles"],
                                    report["g5_24h"]) else 3
    except Exception:
        print("M1_G4_G5_READONLY_REJECTED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
