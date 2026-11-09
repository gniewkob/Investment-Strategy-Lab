"""v0.28 chronological decision-stability audit over the existing v0.17 journal.

Unlike v0.26/27 unordered stress scenarios, this examines *ordered* research
snapshots. It does not evaluate next-month returns, PIT provenance or trades.
Declared input may be synthetic or real unqualified research; never promote it.
"""
from __future__ import annotations

import argparse
import json

from scripts.research_decision_controller_v15 import decide, _unchanged_prefix
from scripts.research_forward_journal_v17 import run_journal
from scripts.research_decision_pipeline_v16 import _load
from scripts.shadow_decision_engine_v05 import (
    ASSETS, MODEL_ASSETS, ShadowInputError, _digest, _utc, _month, _next_month,
)

SCHEMA = "ISL_CHRONOLOGICAL_DECISION_AUDIT_V28_001"
MODE = "EDUCATIONAL_CHRONOLOGICAL_DECISIONS_ONLY"
MAX_CYCLES = 36
GENESIS = "0" * 64


def audit(payload):
    if (not isinstance(payload, dict) or set(payload) != {"mode", "source_kind", "snapshots"}
            or payload["mode"] != MODE
            or payload["source_kind"] not in ("SYNTHETIC_FIXTURE", "UNQUALIFIED_SOURCE_RESEARCH")):
        raise ShadowInputError("exact chronological research-only contract required")
    inputs = payload["snapshots"]
    if not isinstance(inputs, list) or not 2 <= len(inputs) <= MAX_CYCLES:
        raise ShadowInputError("2-36 ordered research snapshots required")
    for snapshot in inputs:
        if not isinstance(snapshot, dict):
            raise ShadowInputError("every snapshot must be an original research manifest")
    # Reuse existing v0.17 chronological receipt chain and v0.15 controller,
    # but deliberately never request an evaluation of forward returns.
    v17 = run_journal({"mode": "EDUCATIONAL_PROSPECTIVE_RESEARCH_ONLY",
                       "cycles": [{"current": doc, "forward_reference": None}
                                  for doc in inputs]})
    counts = {m: {"hold_months": 0, "candidate_months": 0,
                  "status_transitions": 0, "target_changes": 0,
                  "candidate_regime_changes": 0} for m in MODEL_ASSETS}
    entries = []
    prior_doc = None
    prior_state = None
    chain = GENESIS
    for i, doc in enumerate(inputs):
        when = _utc(doc["as_of_utc"])
        if prior_doc is not None:
            prior_when = _utc(prior_doc["as_of_utc"])
            if _month(when.strftime("%Y-%m")) != _next_month(
                    _month(prior_when.strftime("%Y-%m"))):
                raise ShadowInputError("snapshots must represent consecutive decision months")
            # Across shared source families, an updated original history must
            # extend the previously observed prefix by exactly one new month.
            # Never silently accept rewritten historical source levels.
            for asset in ASSETS:
                prev_source = prior_doc.get("series", {}).get(asset)
                new_source = doc.get("series", {}).get(asset)
                if prev_source is not None and new_source is not None:
                    if not _unchanged_prefix(prior_doc, doc, asset):
                        raise ShadowInputError("shared source historical prefix changed: " + asset)
        result = decide(doc, prior_doc)
        if result["controller_receipt_sha256"] != (
                _digest({k:v for k,v in result.items()
                         if k != "controller_receipt_sha256"})):
            raise ShadowInputError("controller fingerprint mismatch")
        # Confirm exactly the v0.17 chained snapshot, no manual source
        # reconstruction or retroactive prospective attribution.
        journal_receipt = v17["receipts"][i]
        if (journal_receipt["cycle_sha256"] is None or
                journal_receipt["model_statuses"] != {
                    m: result["model_states"][m]["status"] for m in MODEL_ASSETS}):
            raise ShadowInputError("v0.17 journal/controller reconciliation mismatch")
        states = {}
        for model in MODEL_ASSETS:
            row = result["model_states"][model]
            status = row["status"]
            stats = counts[model]
            stats["hold_months" if status == "HOLD_CASH" else "candidate_months"] += 1
            old = prior_state["model_states"][model] if prior_state is not None else None
            if old:
                stats["status_transitions"] += int(status != old["status"])
                stats["target_changes"] += int(row["virtual_target"] != old["virtual_target"])
                if (model == "M3_TACTICAL" and status == old["status"] ==
                        "PAPER_CANDIDATE_ONLY" and
                        row["raw_v05_signal"] != old["raw_v05_signal"]):
                    stats["candidate_regime_changes"] += 1
            states[model] = {
                "status": status, "reason": row["reason"],
                "virtual_target": row["virtual_target"],
                "raw_signal_if_any": row["raw_v05_signal"],
            }
        entry = {
            "index": i + 1, "decision_month": when.strftime("%Y-%m"),
            "decision_at_utc": when.isoformat(),
            "manifest_sha256": _digest(doc),
            "controller_sha256": result["controller_receipt_sha256"],
            "journal_v17_receipt_sha256": journal_receipt["receipt_sha256"],
            "previous_audit_receipt_sha256": chain,
            "model_states": states,
        }
        entry["audit_receipt_sha256"] = _digest(entry)
        chain = entry["audit_receipt_sha256"]
        entries.append(entry)
        prior_doc, prior_state = doc, result
    output = {
        "schema": SCHEMA, "mode": MODE, "source_kind": payload["source_kind"],
        "status": "CHRONOLOGICAL_RESEARCH_STABILITY_ONLY_NOT_OOS",
        "decision_months": len(entries), "adjacent_monthly_transitions": len(entries) - 1,
        "model_counts": counts, "receipts": entries,
        "v17_journal_sha256": v17["journal_sha256"],
        "audit_head_sha256": chain,
        "market_turnover_measured": False,
        "forward_returns_evaluated": False,
        "independent_source_and_pit_certified": False,
        "investment_performance_or_alpha_proven": False,
        "real_execution_authorized": False,
        "orders_sent": 0, "paper_fills": 0, "database_writes": 0,
        "financial_operations": 0,
    }
    output["audit_sha256"] = _digest(output)
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",required=True)
    args=p.parse_args()
    result=audit(_load(args.input))
    print("ISL_CHRONOLOGICAL_DECISION_V28="+
          json.dumps(result,sort_keys=True,separators=(",",":")))


if __name__=="__main__":
    main()
