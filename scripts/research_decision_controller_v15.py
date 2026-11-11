"""v0.15 research-only decision controller over immutable M1/M2/M3 policy.

This orchestrates the existing v0.5 source gates; it does not issue orders,
create paper fills, or infer market profitability. For M3, a change of
momentum regime requires two *independently provided consecutive* monthly
source snapshots with matching historical prefixes. It is not a proof of
point-in-time publication or independent source identity.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from scripts.shadow_decision_engine_v05 import (
    ASSETS, MODEL_ASSETS, ShadowInputError, _digest, _month, _next_month,
    _utc, evaluate,
)

SCHEMA = "ISL_RESEARCH_DECISION_CONTROLLER_V15_001"
POLICY = "V15_CONSECUTIVE_M3_CONFIRMATION_001"
SIGNALS = {"MOMENTUM_3M_RISK_ON", "MOMENTUM_3M_RISK_OFF"}
NO_ACTION = {"CASH_PLN": "1"}


def _last_month(manifest, series_code):
    series = manifest.get("series", {})
    values = series.get(series_code, {}).get("observations", [])
    return _month(values[-1]["month"]) if values else None


def _unchanged_prefix(before, current, series_code):
    old = before.get("series", {}).get(series_code)
    new = current.get("series", {}).get(series_code)
    if not isinstance(old, dict) or not isinstance(new, dict):
        return False
    historical = old["observations"]
    updated = new["observations"]
    if not historical or len(updated) != len(historical) + 1:
        return False
    # Exact source observation and release-timestamp equality. Revisions
    # require a separate, explicitly approved research branch, not silent
    # promotion to the decision engine.
    return historical == updated[:-1]


def decide(current, previous=None):
    if not isinstance(current, dict):
        raise ShadowInputError("current raw research manifest required")
    if previous is not None and not isinstance(previous, dict):
        raise ShadowInputError("previous manifest must be a JSON object")
    current_eval = evaluate(current)
    previous_eval = evaluate(previous) if previous is not None else None
    current_at = _utc(current["as_of_utc"])
    if previous_eval is not None:
        prev_at = _utc(previous["as_of_utc"])
        if prev_at >= current_at:
            raise ShadowInputError("previous decision must precede current")
        if (prev_at.year, prev_at.month) == (current_at.year, current_at.month):
            raise ShadowInputError("previous snapshot must have different decision month")
    models = {}
    for model in MODEL_ASSETS:
        raw = current_eval["model_decisions"][model]
        if raw["status"] != "VIRTUAL_TARGET_ONLY":
            models[model] = {
                "status": "HOLD_CASH",
                "reason": "CURRENT_SOURCE_GATES_BLOCKED",
                "blockers": raw["blockers"],
                "virtual_target": dict(NO_ACTION),
                "raw_v05_signal": None,
                "previous_confirmation": False,
            }
            continue
        if model != "M3_TACTICAL":
            models[model] = {
                "status": "PAPER_CANDIDATE_ONLY",
                "reason": "FROZEN_STATIC_POLICY_AND_CURRENT_SOURCES_ELIGIBLE",
                "blockers": {},
                "virtual_target": raw["target"],
                "raw_v05_signal": raw["reason"],
                "previous_confirmation": False,
            }
            continue
        # Do not equate a single as-of manifest with a repeated prospective
        # signal. Two consecutive closed-month research snapshots are required.
        reason = "PREVIOUS_SNAPSHOT_MISSING"
        confirmed = False
        if previous_eval is not None:
            prior = previous_eval["model_decisions"][model]
            prior_last = _last_month(previous, "GLOBAL_EQUITY_TR_PLN")
            now_last = _last_month(current, "GLOBAL_EQUITY_TR_PLN")
            if (prior["status"] != "VIRTUAL_TARGET_ONLY"
                    or prior_last is None or now_last is None):
                reason = "PREVIOUS_SOURCES_INELIGIBLE"
            elif now_last != _next_month(prior_last):
                reason = "NONCONSECUTIVE_MONTHLY_SNAPSHOTS"
            elif not all(_unchanged_prefix(previous, current, a) for a in ASSETS):
                reason = "HISTORICAL_OBSERVATIONS_REVISED_OR_MISSING"
            elif raw["reason"] not in SIGNALS or prior["reason"] not in SIGNALS:
                raise ShadowInputError("unexpected M3 frozen regime signal")
            elif raw["reason"] != prior["reason"]:
                reason = "REGIME_CHANGE_AWAIT_CONFIRMATION"
            else:
                confirmed = True
                reason = "TWO_CONSECUTIVE_RESEARCH_SIGNALS"
        models[model] = {
            "status": "PAPER_CANDIDATE_ONLY" if confirmed else "HOLD_CASH",
            "reason": reason,
            "blockers": {} if confirmed else {"M3_CONFIRMATION": [reason]},
            "virtual_target": raw["target"] if confirmed else dict(NO_ACTION),
            "raw_v05_signal": raw["reason"],
            "previous_confirmation": confirmed,
        }
    eligible = [m for m, state in models.items() if state["status"] == "PAPER_CANDIDATE_ONLY"]
    result = {
        "schema": SCHEMA,
        "policy_version": POLICY,
        "status": ("RESEARCH_PAPER_CANDIDATES_ONLY" if eligible
                   else "HOLD_CASH_NO_QUALIFIED_DECISION"),
        "current_as_of_utc": current_at.isoformat(),
        "current_source_manifest_sha256": _digest(current),
        "current_v05_receipt_sha256": current_eval["decision_fingerprint_sha256"],
        "previous_source_manifest_sha256": _digest(previous) if previous is not None else None,
        "previous_v05_receipt_sha256": (
            previous_eval["decision_fingerprint_sha256"] if previous_eval is not None else None),
        "model_states": models,
        "paper_candidates": eligible,
        "source_blockers": {
            code: check["reasons"]
            for code, check in current_eval["source_readiness"].items()
            if check["status"] != "RESEARCH_ELIGIBLE_DECLARED"
        },
        "source_rights_independently_certified": False,
        "historical_point_in_time_certified": False,
        "independent_capture_certified": False,
        "investment_performance_proven": False,
        "market_execution_authorized": False,
        "orders_sent": 0,
        "paper_fills": 0,
        "financial_operations": 0,
        "database_writes": 0,
    }
    result["controller_receipt_sha256"] = _digest(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    out = decide(
        json.loads(args.current.read_text(encoding="utf-8")),
        json.loads(args.previous.read_text(encoding="utf-8"))
        if args.previous else None,
    )
    print("ISL_RESEARCH_CONTROLLER_V15=" +
          json.dumps(out, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
