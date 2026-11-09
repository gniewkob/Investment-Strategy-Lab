"""v0.27 deterministic synthetic-only quality metrics and rejection gates."""
from copy import deepcopy
import unittest

from scripts.research_decision_quality_v27 import assess, MODE
from scripts.shadow_decision_engine_v05 import ShadowInputError
from tests.test_research_decision_robustness_v26 import fixture

TRUTH = {
    "BASELINE":"RISK_ON",
    "MISSING_EQUITY":"RISK_ON",
    "UNVERIFIED_GOLD":"RISK_ON",
    "RISK_OFF_TRANSITION":"RISK_OFF",
    "HISTORICAL_REVISION":"RISK_ON",
}


def sample():
    return {"mode": MODE, "robustness_suite": fixture(), "truth": dict(TRUTH)}


class SyntheticDecisionQualityV27Tests(unittest.TestCase):
    def test_observed_abstentions_are_not_in_confusion_matrix(self):
        result=assess(sample())
        self.assertEqual(result["synthetic_scenarios"],5)
        self.assertEqual(result["directional_calls"],1)
        self.assertEqual(result["abstentions"],4)
        self.assertEqual(result["synthetic_directional_coverage_percent_floor"],20)
        self.assertEqual(result["correct_directional_calls"],1)
        self.assertEqual(result["wrong_directional_calls"],0)
        self.assertEqual(result["two_class_confusion_matrix_excluding_abstentions"][
            "RISK_ON"]["RISK_ON"],1)
        self.assertEqual(result["status"],"SYNTHETIC_ACCEPTANCE_CHECKS_PASS")
        self.assertFalse(result["market_turnover_or_regime_change_frequency_measured"])
        self.assertFalse(result["real_market_predictive_accuracy_measured"])
        self.assertEqual(result["financial_operations"],0)

    def test_false_directional_label_fails_acceptance(self):
        case=sample()
        case["truth"]["BASELINE"]="RISK_OFF"
        result=assess(case)
        self.assertEqual(result["wrong_directional_calls"],1)
        self.assertEqual(result["status"],"SYNTHETIC_ACCEPTANCE_CHECKS_FAIL")
        self.assertIn("SYNTHETIC_DIRECTIONAL_MISMATCH",result["failed_checks"])
        self.assertEqual(result["two_class_confusion_matrix_excluding_abstentions"][
            "RISK_OFF"]["RISK_ON"],1)

    def test_missing_required_fail_close_case_is_rejected_at_gate(self):
        case=sample()
        case["robustness_suite"]["scenarios"]=[
            s for s in case["robustness_suite"]["scenarios"]
            if s["name"]!="HISTORICAL_REVISION"]
        case["truth"].pop("HISTORICAL_REVISION")
        result=assess(case)
        self.assertIn("REQUIRED_TEST_CASE_MISSING_HISTORICAL_REVISION",
                      result["failed_checks"])
        self.assertEqual(result["status"],"SYNTHETIC_ACCEPTANCE_CHECKS_FAIL")

    def test_incorrect_or_incomplete_truth_contract_rejected(self):
        case=sample()
        case["truth"].pop("BASELINE")
        with self.assertRaisesRegex(ShadowInputError,"ground-truth"):
            assess(case)
        case=sample()
        case["truth"]["BASELINE"]="GAIN_50_PERCENT"
        with self.assertRaisesRegex(ShadowInputError,"ground-truth"):
            assess(case)

    def test_determinism_and_no_mutation(self):
        case=sample()
        original=deepcopy(case)
        self.assertEqual(assess(case),assess(deepcopy(case)))
        self.assertEqual(case,original)
        self.assertEqual(len(assess(case)["quality_receipt_sha256"]),64)

    def test_live_mode_or_invalid_scenario_rejected(self):
        case=sample()
        case["mode"]="LIVE_TRADING"
        with self.assertRaisesRegex(ShadowInputError,"synthetic quality"):
            assess(case)
        case=sample()
        case["robustness_suite"]["scenarios"][0]["expected_statuses"]["M3_TACTICAL"]="HOLD_CASH"
        with self.assertRaisesRegex(ShadowInputError,"expectation mismatch"):
            assess(case)

    def test_extra_fields_and_data_lookahead_rejected(self):
        case=sample()
        case["authorized_order"]=True
        with self.assertRaisesRegex(ShadowInputError,"exact synthetic"):
            assess(case)
        case=sample()
        case["robustness_suite"]["scenarios"][0]["current"]["as_of_utc"]="2026-10-01T00:00:00+00:00"
        with self.assertRaises(ShadowInputError):
            assess(case)


if __name__=="__main__":
    unittest.main()
