"""Tamper-evident sequence of educational shadow receipts, with no trades or P&L.

The chain verifies submitted snapshots, chronological order and the existing
single-period forward gates. It does not certify external issuance, source
licensing, publication vintages, investability or genuine unattended capture.
"""
from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

from scripts.shadow_decision_engine_v05 import ShadowInputError, _digest, _utc
from scripts.shadow_forward_evaluation_v05 import evaluate_forward

MODE = "EDUCATIONAL_SHADOW_JOURNAL_ONLY"
GENESIS = "0" * 64
MAX_ENTRIES = 120


def build_journal(payload):
    if not isinstance(payload, dict) or set(payload) != {"mode", "entries"}:
        raise ShadowInputError("journal expects mode and entries")
    if payload["mode"] != MODE:
        raise ShadowInputError("only educational shadow journal is allowed")
    entries = payload["entries"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ENTRIES:
        raise ShadowInputError("journal entries must be bounded and nonempty")
    chain = GENESIS
    previous_forward = None
    seen_decisions = set()
    receipts = []
    count = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {"decision", "forward_reference"}:
            raise ShadowInputError("invalid journal entry schema")
        decision = entry["decision"]
        forward = entry["forward_reference"]
        if not isinstance(decision, dict) or not isinstance(forward, dict):
            raise ShadowInputError("journal entries must contain objects")
        fingerprint = decision.get("decision_fingerprint_sha256")
        if fingerprint in seen_decisions:
            raise ShadowInputError("duplicate frozen decision")
        result = evaluate_forward(decision, forward)
        decided = _utc(decision["as_of_utc"])
        finished = _utc(forward["as_of_utc"])
        if previous_forward is not None and decided <= previous_forward:
            raise ShadowInputError("overlapping or retrospectively sequenced decisions")
        if finished <= decided:
            raise ShadowInputError("forward evaluation must follow decision")
        if previous_forward is not None and finished <= previous_forward:
            raise ShadowInputError("non-monotonic forward evaluations")
        seen_decisions.add(fingerprint)
        statuses = {model: data["status"] for model, data in result["results"].items()}
        for model, status in statuses.items():
            count.setdefault(model, {})
            count[model][status] = count[model].get(status, 0) + 1
        receipt = {
            "sequence": index + 1,
            "previous_receipt_sha256": chain,
            "decision_sha256": fingerprint,
            "forward_input_sha256": _digest(forward),
            "forward_result_sha256": result["receipt_sha256"],
            "decision_as_of_utc": decided.isoformat(),
            "forward_as_of_utc": finished.isoformat(),
            "model_statuses": statuses,
        }
        receipt["receipt_sha256"] = _digest(receipt)
        chain = receipt["receipt_sha256"]
        receipts.append(receipt)
        previous_forward = finished
    output = {
        "mode": MODE,
        "status": "AUDIT_CHAIN_ONLY_NOT_PERFORMANCE_EVIDENCE",
        "entries": len(receipts),
        "genesis_sha256": GENESIS,
        "head_sha256": chain,
        "receipts": receipts,
        "model_status_counts": count,
        "historical_pit_certified": False,
        "source_licensing_independently_certified": False,
        "independent_capture_attested": False,
        "investment_performance_proven": False,
        "sharpe": None,
        "drawdown": None,
        "orders_sent": 0,
        "paper_fills": 0,
        "database_writes": 0,
    }
    output["journal_sha256"] = _digest(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_journal(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("ISL_SHADOW_JOURNAL_V06=" + json.dumps(
        {"status": result["status"], "entries": result["entries"],
         "head_sha256": result["head_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
