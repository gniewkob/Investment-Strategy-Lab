"""v0.17 prospective research-cycle journal, not an investment system.

Replay immutable, chronologically ordered research manifests. Freeze an M1-M3
controller decision at each as-of, optionally evaluate on a strictly later
month using the existing v0.5 forward validator. Never treat self-declared
source verification as independent original/PIT certification.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.research_decision_pipeline_v16 import _load, run_cycle
from scripts.shadow_decision_engine_v05 import (
    MODEL_ASSETS, ShadowInputError, _digest, _utc, evaluate,
)
from scripts.shadow_forward_evaluation_v05 import evaluate_forward

SCHEMA = "ISL_FORWARD_RESEARCH_JOURNAL_V17_001"
MAX_CYCLES = 120
GENESIS = "0" * 64


def run_journal(payload):
    if not isinstance(payload, dict) or set(payload) != {"mode", "cycles"}:
        raise ShadowInputError("journal requires exact mode and cycles")
    if payload["mode"] != "EDUCATIONAL_PROSPECTIVE_RESEARCH_ONLY":
        raise ShadowInputError("non-financial research mode required")
    cycles = payload["cycles"]
    if not isinstance(cycles, list) or not 1 <= len(cycles) <= MAX_CYCLES:
        raise ShadowInputError("journal cycles must be nonempty and bounded")
    receipts = []
    previous = None
    previous_at = None
    latest_forward_at = None
    forward_counts = {model: 0 for model in MODEL_ASSETS}
    declared_source_periods = set()
    chain = GENESIS
    seen = set()
    forward_vintages = set()
    for i, item in enumerate(cycles):
        if not isinstance(item, dict) or set(item) != {
                "current", "forward_reference"}:
            raise ShadowInputError("cycle needs current and forward_reference")
        current = item["current"]
        forward = item["forward_reference"]
        if not isinstance(current, dict) or (
                forward is not None and not isinstance(forward, dict)):
            raise ShadowInputError("invalid research inputs")
        current_at = _utc(current.get("as_of_utc"))
        if previous_at is not None and current_at <= previous_at:
            raise ShadowInputError("decisions must strictly increase")
        if latest_forward_at is not None and current_at <= latest_forward_at:
            raise ShadowInputError("new decision must postdate prior evaluated month")
        fingerprint = _digest(current)
        if fingerprint in seen:
            raise ShadowInputError("duplicate decision manifest")
        seen.add(fingerprint)
        cycle = run_cycle(current=current, previous=previous)
        evaluated = {}
        forward_hash = None
        observed_at = None
        if forward is not None:
            if forward.get("source_vintage") not in (
                    "SYNTHETIC_OFFLINE_FIXTURE", "FUTURE_PROSPECTIVE_RESEARCH"):
                raise ShadowInputError("forward vintage must be explicit")
            forward_vintages.add(forward["source_vintage"])
            frozen = evaluate(current)
            result = evaluate_forward(frozen, forward)
            forward_hash = result["receipt_sha256"]
            observed_at = _utc(forward["as_of_utc"])
            # The old v0.5 forward validator does not know v0.15's added
            # confirmation gate. Never calculate M3 attribution if v0.15
            # marked its target HOLD_CASH.
            for model in MODEL_ASSETS:
                if model not in cycle["paper_candidates"]:
                    evaluated[model] = {
                        "status": "NOT_EVALUABLE_CONTROLLER_HOLD",
                        "hypothetical_net_return": None,
                    }
                else:
                    item_result = result["results"][model]
                    status = item_result["status"]
                    if status == "ONE_FORWARD_REFERENCE_PERIOD_RESEARCH_ONLY":
                        forward_counts[model] += 1
                    evaluated[model] = {
                        "status": status,
                        "hypothetical_net_return": (
                            item_result.get("hypothetical_net_return_after_assumed_costs")
                            if status == "ONE_FORWARD_REFERENCE_PERIOD_RESEARCH_ONLY" else None),
                    }
            latest_forward_at = observed_at
        for model in cycle["paper_candidates"]:
            state = cycle["model_decisions"][model]
            if state["status"] != "PAPER_CANDIDATE_ONLY":
                raise ShadowInputError("controller inconsistency")
        receipt = {
            "index": i + 1,
            "previous_receipt_sha256": chain,
            "decision_as_of_utc": current_at.isoformat(),
            "manifest_sha256": fingerprint,
            "cycle_sha256": cycle["cycle_receipt_sha256"],
            "paper_candidates": cycle["paper_candidates"],
            "model_statuses": {
                model: cycle["model_decisions"][model]["status"]
                for model in MODEL_ASSETS
            },
            "forward_receipt_sha256": forward_hash,
            "forward_evaluated_at_utc": observed_at.isoformat() if observed_at else None,
            "forward_models": evaluated,
        }
        receipt["receipt_sha256"] = _digest(receipt)
        chain = receipt["receipt_sha256"]
        receipts.append(receipt)
        previous_at = current_at
        previous = current
        declared_source_periods.add(current_at.strftime("%Y-%m"))
    # No automatic truth-upgrade: source originalness, rights, true PIT,
    # and independent archival capture cannot be certified from JSON.
    status = (
        "SYNTHETIC_ONLY_NO_MARKET_ACCEPTANCE"
        if forward_vintages == {"SYNTHETIC_OFFLINE_FIXTURE"}
        else "FORWARD_REFERENCE_OBSERVED_NOT_INDEPENDENTLY_ATTESTED"
        if any(forward_counts.values())
        else "NOT_RUN_NO_EVALUABLE_FORWARD_MARKET_DATA"
    )
    output = {
        "schema": SCHEMA,
        "status": status,
        "cycles_completed": len(receipts),
        "distinct_decision_months": len(declared_source_periods),
        "forward_evaluable_periods_per_model": forward_counts,
        "minimum_independent_forward_periods_for_acceptance": 2,
        "market_data_acceptance": "BLOCKED_INDEPENDENT_SOURCE_AND_PIT_EVIDENCE",
        "profitability_or_alpha_proven": False,
        "real_orders": 0, "paper_fills": 0,
        "financial_operations": 0, "database_writes": 0,
        "genesis_sha256": GENESIS, "journal_head_sha256": chain,
        "receipts": receipts,
    }
    output["journal_sha256"] = _digest(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    result = run_journal(_load(args.input))
    print("ISL_FORWARD_JOURNAL_V17=" +
          json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
