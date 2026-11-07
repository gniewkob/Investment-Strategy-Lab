"""v0.22 freeze a private Vanguard/NBP reference research protocol before new observations.

A frozen protocol is evidence of a declared rule, NOT independent archival
timestamp proof or an investment signal. This module never computes forward
returns from an already-known source month and does not promote NAV to M1.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re

from scripts.conditional_m1_nav_analytics_v21 import evaluate as evaluate_v21
from scripts.reference_archive_calendar_v04 import _digest

SCHEMA = "ISL_NAV_FORWARD_FREEZE_V22_001"
POLICY = {
    "mode": "EDUCATIONAL_REFERENCE_ONLY",
    "strategy": "MONTHLY_100_PLN_FRACTIONAL_NAV_RESEARCH",
    "monthly_contribution_pln": "100",
    "base_fee_bps": "20",
    "base_slippage_bps": "10",
    "comparison": "ZERO_INTEREST_PLN_CASH",
    "monthly_observation": "LAST_VALID_OFFICIAL_NAV_PLUS_EXACT_DATE_NBP_USDPLN",
    "execution_status": "NO_REAL_ORDERS_OR_FILLS",
    "future_month_handling": "NEW_ORIGINAL_SOURCE_AND_PUBLISHED_AFTER_FREEZE_REQUIRED",
}
SHA = re.compile(r"^[0-9a-f]{64}$")


def _clock(clock):
    now = clock()
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("timezone-aware clock required")
    return now.astimezone(timezone.utc)


def freeze(artifact, *, clock=lambda: datetime.now(timezone.utc)):
    analytics = evaluate_v21(artifact)
    now = _clock(clock)
    if not (date(2026, 11, 1) <= now.date() < date(2026, 12, 1)):
        raise ValueError("freeze must occur during November 2026 before first new complete month")
    if analytics["last_month"] != "2026-10" or analytics["months"] != 60:
        raise ValueError("missing expected cutoff")
    out = {
        "schema": SCHEMA,
        "status": "FROZEN_PENDING_FIRST_FUTURE_MONTH",
        "frozen_at_utc": now.isoformat(),
        "last_known_month": "2026-10",
        "first_forward_month": "2026-11",
        "source_evidence_sha256": artifact["evidence_sha256"],
        "original_nav_file_sha256": artifact["nav_candidate_file_sha256"],
        "baseline_analytics_v21_sha256": analytics["analytics_receipt_sha256"],
        "declared_policy": dict(POLICY),
        "forward_qualified_months": 0,
        "forward_observations": [],
        "independent_time_anchor_verified": False,
        "historical_pit_certified": False,
        "source_rights_independently_certified": False,
        "executable_market_fills_verified": False,
        "strict_m1_model_qualified": False,
        "alpha_or_future_performance_proven": False,
        "orders_sent": 0,
        "financial_operations": 0,
        "database_writes": 0,
    }
    out["freeze_receipt_sha256"] = _digest(out)
    return out


def verify_pending(document, *, clock=lambda: datetime.now(timezone.utc)):
    if not isinstance(document, dict):
        raise ValueError("freeze document object required")
    copy = dict(document)
    declared = copy.pop("freeze_receipt_sha256", None)
    if not isinstance(declared, str) or not SHA.fullmatch(declared) or _digest(copy) != declared:
        raise ValueError("freeze SHA-256 mismatch")
    if document.get("schema") != SCHEMA or document.get("declared_policy") != POLICY:
        raise ValueError("unsupported frozen research policy")
    for k in ("source_evidence_sha256", "baseline_analytics_v21_sha256",
              "original_nav_file_sha256"):
        if not isinstance(document.get(k), str) or not SHA.fullmatch(document[k]):
            raise ValueError("missing frozen source sha")
    if (document.get("last_known_month") != "2026-10"
            or document.get("first_forward_month") != "2026-11"
            or document.get("status") != "FROZEN_PENDING_FIRST_FUTURE_MONTH"
            or document.get("forward_qualified_months") != 0
            or document.get("forward_observations") != []
            or document.get("independent_time_anchor_verified") is not False
            or document.get("strict_m1_model_qualified") is not False
            or document.get("orders_sent") != 0
            or document.get("financial_operations") != 0
            or document.get("database_writes") != 0):
        raise ValueError("cannot claim forward evidence or M1 qualification")
    try:
        at = datetime.fromisoformat(document["frozen_at_utc"])
    except (ValueError, KeyError, TypeError) as e:
        raise ValueError("invalid freeze timestamp") from e
    if at.tzinfo is None or at.utcoffset().total_seconds() != 0:
        raise ValueError("UTC freeze timestamp required")
    now = _clock(clock)
    if at > now:
        raise ValueError("freeze timestamp cannot be in future")
    if not (date(2026, 11, 1) <= at.date() < date(2026, 12, 1)):
        raise ValueError("invalid freeze calendar date")
    return {"status": "PENDING_NO_PROSPECTIVE_DATA",
            "freeze_receipt_sha256": declared,
            "forward_qualified_months": 0, "strict_m1_model_qualified": False,
            "independent_time_anchor_verified": False,
            "financial_operations": 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--nav-receipt", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    src, dest = args.nav_receipt, args.out
    if (src.is_symlink() or not src.is_file() or src.stat().st_size > 3_000_000
            or dest.exists() or dest.is_symlink() or src.resolve() == dest.resolve()):
        raise ValueError("private source must exist; output must not overwrite any file")
    source = json.loads(src.read_text(encoding="utf-8"))
    frozen = freeze(source)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Atomic exclusive creation; no silent replacement.
    with dest.open("x", encoding="utf-8") as f:
        json.dump(frozen, f, sort_keys=True, indent=2)
        f.write("\n")
    print("ISL_NAV_FORWARD_FREEZE_V22=" +
          json.dumps(verify_pending(frozen), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
