"""v0.26 all-synthetic decision-resilience audit; never validates real sources."""
from copy import deepcopy
import unittest

from scripts.research_decision_robustness_v26 import evaluate_suite, MODE
from scripts.shadow_decision_engine_v05 import EQUITY, GOLD, ShadowInputError
from tests.test_research_decision_controller_v15 import pair

M1="M1_GLOBAL_EQ"
M2="M2_DIVERSIFIED"
M3="M3_TACTICAL"
H="HOLD_CASH"
P="PAPER_CANDIDATE_ONLY"


def fixture():
    current, previous = pair()
    baseline = {
        "name": "BASELINE", "current": current, "previous": previous,
        "expected_statuses": {M1:P,M2:P,M3:P},
    }
    missing = deepcopy(baseline)
    missing["name"] = "MISSING_EQUITY"
    missing["current"]["series"].pop(EQUITY)
    missing["expected_statuses"] = {M1:H,M2:H,M3:H}
    unverified = deepcopy(baseline)
    unverified["name"] = "UNVERIFIED_GOLD"
    unverified["current"]["series"][GOLD]["rights_status"] = "UNVERIFIED"
    unverified["expected_statuses"] = {M1:P,M2:H,M3:H}
    transition = deepcopy(baseline)
    transition["name"] = "RISK_OFF_TRANSITION"
    transition["current"]["series"][EQUITY]["observations"][-1]["level_pln"] = "400"
    transition["expected_statuses"] = {M1:P,M2:P,M3:H}
    revision = deepcopy(baseline)
    revision["name"] = "HISTORICAL_REVISION"
    revision["current"]["series"][EQUITY]["observations"][20]["level_pln"] = "1250"
    revision["expected_statuses"] = {M1:P,M2:P,M3:H}
    return {"mode":MODE,"scenarios":[baseline,missing,unverified,transition,revision]}


class DecisionResilienceV26Tests(unittest.TestCase):
    def test_five_synthetic_robustness_scenarios_and_counters(self):
        r=evaluate_suite(fixture())
        self.assertEqual(r["scenario_count"],5)
        self.assertEqual(r["counts"][M1]["paper_candidate_only"],4)
        self.assertEqual(r["counts"][M2]["paper_candidate_only"],3)
        self.assertEqual(r["counts"][M3]["paper_candidate_only"],1)
        self.assertEqual(r["counts"][M3]["hold_cash"],4)
        self.assertEqual(r["financial_operations"],0)
        self.assertFalse(r["prospective_out_of_sample_market_returns_measured"])
        self.assertFalse(r["model_alpha_or_profitability_proven"])

    def test_expected_regime_change_and_no_silent_revision(self):
        r=evaluate_suite(fixture())
        byname={x["name"]:x for x in r["scenarios"]}
        self.assertEqual(byname["RISK_OFF_TRANSITION"]["model_states"][M3]["reason"],
                         "REGIME_CHANGE_AWAIT_CONFIRMATION")
        self.assertEqual(byname["HISTORICAL_REVISION"]["model_states"][M3]["reason"],
                         "HISTORICAL_OBSERVATIONS_REVISED_OR_MISSING")
        self.assertEqual(byname["UNVERIFIED_GOLD"]["model_states"][M3]["status"],H)
        self.assertEqual(byname["BASELINE"]["model_states"][M3]["status"],P)

    def test_same_suite_is_reproducible_and_unmodified(self):
        suite=fixture()
        original=deepcopy(suite)
        self.assertEqual(evaluate_suite(suite),evaluate_suite(deepcopy(suite)))
        self.assertEqual(suite,original)
        self.assertEqual(len(evaluate_suite(suite)["research_receipt_sha256"]),64)

    def test_mismatch_expected_states_fail_closed(self):
        suite=fixture()
        suite["scenarios"][1]["expected_statuses"][M1]=P
        with self.assertRaisesRegex(ShadowInputError,"expectation mismatch"):
            evaluate_suite(suite)

    def test_duplicate_and_missing_baseline_blocked(self):
        suite=fixture()
        suite["scenarios"][1]["name"]="BASELINE"
        with self.assertRaisesRegex(ShadowInputError,"unique"):
            evaluate_suite(suite)
        suite=fixture()
        suite["scenarios"][0]["name"]="NOT_BASELINE"
        with self.assertRaisesRegex(ShadowInputError,"first scenario"):
            evaluate_suite(suite)

    def test_real_trading_mode_and_extra_keys_blocked(self):
        suite=fixture()
        suite["mode"]="LIVE_TRADING"
        with self.assertRaisesRegex(ShadowInputError,"synthetic"):
            evaluate_suite(suite)
        suite=fixture()
        suite["scenarios"][0]["current"]["mode"]="LIVE_TRADING"
        with self.assertRaises(ShadowInputError):
            evaluate_suite(suite)
        suite=fixture()
        suite["scenarios"][0]["real_orders"]=True
        with self.assertRaisesRegex(ShadowInputError,"exact synthetic"):
            evaluate_suite(suite)

    def test_invalid_cardinality_and_source_time_blocked(self):
        suite=fixture()
        suite["scenarios"]=suite["scenarios"][:1]
        with self.assertRaisesRegex(ShadowInputError,"bounded"):
            evaluate_suite(suite)
        suite=fixture()
        suite["scenarios"][0]["current"]["series"][EQUITY]["retrieved_at"] = (
            "2026-12-10T20:00:00+00:00")
        with self.assertRaisesRegex(ShadowInputError,"future retrieval"):
            evaluate_suite(suite)


if __name__=="__main__":
    unittest.main()
