"""Read-only M1 acceptance gate over existing private collector evidence.

No network, launchctl, credentials, write operations or supervisor control.
A PASS here attests only the selected 24h evidence window, not deployment.
"""
import argparse
from bisect import bisect_right
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat

from scripts import unattended_acceptance as acceptance

DAY = 86_400
MAX_LEDGER_BYTES = 64_000_000
MIN_NATURAL_CYCLES = 90
MAX_SAMPLE_AGE = 120


def read_samples(path):
    """Read strictly private, bounded append-only metadata; never read a wallet."""
    path = Path(path)
    acceptance.private_directory(path.parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_size > MAX_LEDGER_BYTES):
            raise ValueError("UNSAFE_EVIDENCE")
        raw = handle.read(MAX_LEDGER_BYTES + 1)
    if not raw or len(raw) > MAX_LEDGER_BYTES:
        raise ValueError("BAD_EVIDENCE_SIZE")
    rows = []
    last = float("-inf")
    for line in raw.splitlines():
        if not line:
            raise ValueError("BLANK_ROW")
        row = json.loads(line)
        value = row.get("observed_at") if isinstance(row, dict) else None
        if (type(value) not in (int, float) or
                not float("-inf") < value < float("inf") or value <= last):
            raise ValueError("NON_MONOTONIC_EVIDENCE")
        last = value
        rows.append(row)
    return rows


def assess(rows, now):
    """Assess last eligible >=24h ledger slice; preserve full original evidence."""
    if not rows or type(now) not in (int, float):
        raise ValueError("INVALID_WINDOW_INPUT")
    times = [r["observed_at"] for r in rows]
    if any(type(t) not in (int, float) or
           not float("-inf") < t < float("inf") for t in times):
        raise ValueError("INVALID_TIMESTAMPS")
    if any(a >= b for a, b in zip(times, times[1:])):
        raise ValueError("CLOCK_REGRESSION")

    end = times[-1]
    cutoff = end - DAY
    position = max(0, bisect_right(times, cutoff) - 1)
    selected = rows[position:]
    summary = acceptance.summarize(selected)

    reasons = list(summary["reasons"])
    if summary["natural_unique_checkpoints"] < MIN_NATURAL_CYCLES:
        reasons.append("M1_NATURAL_CHECKPOINTS_BELOW_90")
    if (end > now + 5 or now - end > MAX_SAMPLE_AGE):
        reasons.append("M1_LAST_SAMPLE_STALE_OR_FUTURE")
    if any(type(r.get("financial_operations")) is not int or
           r["financial_operations"] != 0 for r in selected):
        reasons.append("M1_FINANCIAL_INVARIANT_FAILED")
    if selected[0]["observed_at"] < cutoff - MAX_SAMPLE_AGE:
        reasons.append("M1_WINDOW_START_UNVERIFIED")

    def count_status(name):
        return sum(r.get("status") == name for r in selected)

    partial_cycles = {
        r.get("checkpoint_at") for r in selected
        if r.get("status") == "PARTIAL"
        and r.get("sources", {}).get("rpc_ethereum") == "PARTIAL"
        and type(r.get("checkpoint_at")) in (int, float)
    }
    gaps = [b-a for a, b in zip(times[position:], times[position+1:])]
    known_rpc = summary.get("http_429_count")
    return {
        "mode": "M1_ROLLING_24H_READ_ONLY_EVIDENCE_V1",
        "status": "PARTIAL" if reasons else "PASS",
        "scope": "METADATA_ONLY_NOT_DEPLOYMENT_OR_PROVIDER_ATTESTATION",
        "start_utc": summary["start_utc"],
        "end_utc": summary["end_utc"],
        "span_seconds": round(summary["span_seconds"], 3),
        "sample_count": len(selected),
        "natural_unique_checkpoints": summary["natural_unique_checkpoints"],
        "invalid_samples": count_status("INVALID"),
        "partial_samples": count_status("PARTIAL"),
        "ethereum_partial_unique_checkpoints": len(partial_cycles),
        "collector_gaps_over_120s": sum(x > 120 or x <= 0 for x in gaps),
        "delayed_cycles_over_1020s": summary["delayed_intervals_over_1020"],
        "http_429_count": known_rpc if type(known_rpc) is int else None,
        "reasons": reasons,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = assess(read_samples(args.samples),
                        datetime.now(timezone.utc).timestamp())
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0 if result["status"] == "PASS" else 3
    except Exception:
        # Do not disclose private path, file rows, or unexpected exception text.
        print("M1_READONLY_EVIDENCE_REJECTED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
