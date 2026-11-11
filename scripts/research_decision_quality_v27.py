"""v0.27 synthetic decision-quality diagnostic, not market prediction validation.

Truth labels are explicitly supplied by an offline test author. A scenario
matrix is NOT a chronology; compare target drift to baseline, never report
transition frequency across independently perturbed scenarios as market
turnover. HOLD_CASH is abstention, not a wrong directional call.
"""
from __future__ import annotations

import argparse
import json

from scripts.research_decision_robustness_v26 import evaluate_suite
from scripts.research_decision_pipeline_v16 import _load
from scripts.shadow_decision_engine_v05 import ShadowInputError, _digest, MODEL_ASSETS

SCHEMA = "ISL_SYNTHETIC_DECISION_QUALITY_V27_001"
MODE = "SYNTHETIC_DECISION_QUALITY_RESEARCH_ONLY"
RISK_ON = "RISK_ON"
RISK_OFF = "RISK_OFF"
LABELS = (RISK_ON, RISK_OFF)
M3 = "M3_TACTICAL"
SIGNAL = {"MOMENTUM_3M_RISK_ON": RISK_ON, "MOMENTUM_3M_RISK_OFF": RISK_OFF}
POLICY = {
    "min_synthetic_scenarios": 5,
    "min_directional_coverage_percent": 20,
    "max_wrong_directional_calls": 0,
    "required_abstention_scenarios": ["MISSING_EQUITY", "HISTORICAL_REVISION",
                                      "RISK_OFF_TRANSITION"],
}


def assess(suite):
    if not isinstance(suite, dict) or set(suite) != {"mode", "robustness_suite", "truth"}:
        raise ShadowInputError("exact synthetic decision-quality contract required")
    if suite["mode"] != MODE:
        raise ShadowInputError("synthetic quality mode required")
    audit = evaluate_suite(suite["robustness_suite"])
    truth = suite["truth"]
    names = audit["scenario_names"]
    if (not isinstance(truth, dict) or set(truth) != set(names)
            or any(x not in LABELS for x in truth.values())):
        raise ShadowInputError("one explicit synthetic ground-truth label per scenario required")
    matrix = {expected: {predicted: 0 for predicted in LABELS}
              for expected in LABELS}
    abstained = {expected: 0 for expected in LABELS}
    held = []
    wrong = []
    called = 0
    shifts = 0
    baseline = audit["scenarios"][0]["model_states"]
    per_scenario = []
    for index, case in enumerate(audit["scenarios"]):
        name = case["name"]
        state = case["model_states"][M3]
        expected = truth[name]
        if state["status"] == "HOLD_CASH":
            abstained[expected] += 1
            held.append(name)
            predicted = None
        else:
            if state["status"] != "PAPER_CANDIDATE_ONLY":
                raise ShadowInputError("unexpected M3 research status")
            predicted = SIGNAL.get(state["reason"].replace("TWO_CONSECUTIVE_RESEARCH_SIGNALS", ""))
            # Controller's raw signal isn't included in v0.26 states. Decode
            # frozen M3 virtual target for approved candidate cases only.
            if predicted is None:
                weights = state["virtual_target"]
                if weights.get("CASH_PLN") == "0" and weights.get("GLOBAL_EQUITY_TR_PLN") == "0.6":
                    predicted = RISK_ON
                elif weights.get("CASH_PLN") == "0.3" and weights.get("GLOBAL_EQUITY_TR_PLN") == "0.3":
                    predicted = RISK_OFF
                else:
                    raise ShadowInputError("unknown frozen M3 synthetic target")
            matrix[expected][predicted] += 1
            called += 1
            if predicted != expected:
                wrong.append(name)
        drift = {
            model: case["model_states"][model]["virtual_target"] !=
                   baseline[model]["virtual_target"]
            for model in MODEL_ASSETS
        }
        if index > 0:
            shifts += int(drift[M3])
        per_scenario.append({
            "scenario": name,
            "synthetic_truth": expected,
            "synthetic_prediction": predicted,
            "m3_abstained": predicted is None,
            "m3_controller_reason": state["reason"],
            "target_differs_from_baseline": drift,
        })
    n = len(names)
    correct = sum(matrix[label][label] for label in LABELS)
    coverage = 100 * called // n
    failures = []
    if n < POLICY["min_synthetic_scenarios"]:
        failures.append("INSUFFICIENT_SYNTHETIC_SCENARIOS")
    if coverage < POLICY["min_directional_coverage_percent"]:
        failures.append("LOW_SYNTHETIC_DIRECTIONAL_COVERAGE")
    if len(wrong) > POLICY["max_wrong_directional_calls"]:
        failures.append("SYNTHETIC_DIRECTIONAL_MISMATCH")
    for required in POLICY["required_abstention_scenarios"]:
        if required not in names:
            failures.append("REQUIRED_TEST_CASE_MISSING_" + required)
        elif required not in held:
            failures.append("FAIL_CLOSED_ABSTENTION_MISSING_" + required)
    out = {
        "schema": SCHEMA,
        "mode": MODE,
        "status": ("SYNTHETIC_ACCEPTANCE_CHECKS_PASS" if not failures
                   else "SYNTHETIC_ACCEPTANCE_CHECKS_FAIL"),
        "synthetic_acceptance_only": True,
        "research_policy": POLICY,
        "failed_checks": failures,
        "synthetic_scenarios": n,
        "directional_calls": called,
        "abstentions": n - called,
        "synthetic_directional_coverage_percent_floor": coverage,
        "correct_directional_calls": correct,
        "wrong_directional_calls": len(wrong),
        "wrong_directional_scenario_names": wrong,
        "two_class_confusion_matrix_excluding_abstentions": matrix,
        "abstentions_by_truth": abstained,
        "target_differences_from_baseline_m3": shifts,
        "market_turnover_or_regime_change_frequency_measured": False,
        "per_scenario": per_scenario,
        "robustness_receipt_sha256": audit["research_receipt_sha256"],
        "real_market_predictive_accuracy_measured": False,
        "real_market_precision_or_recall_measured": False,
        "financial_performance_proven": False,
        "source_rights_or_pit_certified": False,
        "model_qualified_for_financial_execution": False,
        "orders_sent": 0, "paper_fills": 0, "database_writes": 0,
        "financial_operations": 0,
    }
    out["quality_receipt_sha256"] = _digest(out)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--suite", required=True)
    args = p.parse_args()
    result = assess(_load(args.suite))
    print("ISL_DECISION_QUALITY_V27=" +
          json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
