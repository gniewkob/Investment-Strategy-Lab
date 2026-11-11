"""v0.26 decision-resilience audit over explicit synthetic research scenarios.

Evaluates frozen v0.15 controller outputs only. Scenario outcomes are target
stability/readiness classifications, NOT financial returns, profitability,
alpha, broker orders or attestations of first source publication.
"""
from __future__ import annotations

import argparse
import json
import re

from scripts.research_decision_controller_v15 import decide
from scripts.shadow_decision_engine_v05 import MODEL_ASSETS, ShadowInputError, _digest
from scripts.research_decision_pipeline_v16 import _load

SCHEMA = "ISL_DECISION_ROBUSTNESS_V26_001"
MODE = "SYNTHETIC_DECISION_RESILIENCE_RESEARCH_ONLY"
MAX_SCENARIOS = 32
LABEL = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


def evaluate_suite(suite):
    if (not isinstance(suite, dict) or set(suite) != {"mode", "scenarios"}
            or suite["mode"] != MODE):
        raise ShadowInputError("synthetic decision resilience mode required")
    scenarios = suite["scenarios"]
    if not isinstance(scenarios, list) or not 2 <= len(scenarios) <= MAX_SCENARIOS:
        raise ShadowInputError("bounded scenario matrix with baseline required")
    labels = set()
    results = []
    for index, entry in enumerate(scenarios):
        if not isinstance(entry, dict) or set(entry) != {
                "name", "current", "previous", "expected_statuses"}:
            raise ShadowInputError("exact synthetic scenario contract required")
        name = entry["name"]
        if not isinstance(name, str) or not LABEL.fullmatch(name) or name in labels:
            raise ShadowInputError("unique synthetic scenario name required")
        if index == 0 and name != "BASELINE":
            raise ShadowInputError("first scenario must be BASELINE")
        labels.add(name)
        expected = entry["expected_statuses"]
        if (not isinstance(expected, dict) or set(expected) != set(MODEL_ASSETS)
                or any(value not in ("HOLD_CASH", "PAPER_CANDIDATE_ONLY")
                       for value in expected.values())):
            raise ShadowInputError("exact expected model statuses required")
        if (not isinstance(entry["current"], dict) or
                entry["previous"] is not None and
                not isinstance(entry["previous"], dict)):
            raise ShadowInputError("invalid synthetic research manifest")
        decision = decide(entry["current"], entry["previous"])
        states = {model: {
            "status": decision["model_states"][model]["status"],
            "reason": decision["model_states"][model]["reason"],
            "virtual_target": decision["model_states"][model]["virtual_target"],
            "previous_confirmation":
                decision["model_states"][model]["previous_confirmation"],
        } for model in MODEL_ASSETS}
        actual = {model: item["status"] for model, item in states.items()}
        if actual != expected:
            raise ShadowInputError("scenario expectation mismatch: " + name)
        results.append({
            "name": name,
            "model_states": states,
            "controller_sha256": decision["controller_receipt_sha256"],
            "scenario_input_sha256": _digest(entry),
        })
    base = results[0]["model_states"]
    counts = {model: {
        "hold_cash": sum(r["model_states"][model]["status"] == "HOLD_CASH"
                         for r in results),
        "paper_candidate_only": sum(
            r["model_states"][model]["status"] == "PAPER_CANDIDATE_ONLY"
            for r in results),
        "target_changed_from_baseline": sum(
            r["model_states"][model]["virtual_target"] !=
            base[model]["virtual_target"] for r in results[1:]),
    } for model in MODEL_ASSETS}
    output = {
        "schema": SCHEMA,
        "mode": MODE,
        "status": "SYNTHETIC_SOURCE_AND_CONTROLLER_STRESS_TEST_ONLY",
        "scenario_count": len(results),
        "scenario_names": [r["name"] for r in results],
        "counts": counts,
        "scenarios": results,
        "historical_source_rights_independently_certified": False,
        "prospective_out_of_sample_market_returns_measured": False,
        "model_alpha_or_profitability_proven": False,
        "real_market_execution_authorized": False,
        "orders_sent": 0, "paper_fills": 0,
        "financial_operations": 0, "database_writes": 0,
    }
    output["research_receipt_sha256"] = _digest(output)
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--suite", required=True)
    args = p.parse_args()
    output = evaluate_suite(_load(args.suite))
    print("ISL_DECISION_ROBUSTNESS_V26=" +
          json.dumps(output, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
