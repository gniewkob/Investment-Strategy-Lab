"""v0.15 controller: qualified research candidates, never trades."""
from copy import deepcopy
import unittest

from scripts.research_decision_controller_v15 import decide
from scripts.shadow_decision_engine_v05 import ASSETS, EQUITY, GOLD, ShadowInputError
from tests.test_shadow_decision_engine_v05 import sample


def pair(*, downward=False):
    now = sample(down=downward)
    prev = sample(down=downward)
    prev["as_of_utc"] = "2026-10-06T20:00:00+00:00"
    for source in prev["series"].values():
        source["retrieved_at"] = prev["as_of_utc"]
        source["observations"].pop()
    return now, prev


class DecisionControllerV15Tests(unittest.TestCase):
    def test_missing_data_holds_every_model_without_fake_candidate(self):
        state = decide(sample(include=()))
        self.assertEqual(state["status"], "HOLD_CASH_NO_QUALIFIED_DECISION")
        self.assertEqual(state["paper_candidates"], [])
        self.assertEqual(len(state["source_blockers"]), 3)
        self.assertTrue(all(x["status"] == "HOLD_CASH"
                            for x in state["model_states"].values()))
        self.assertEqual(state["financial_operations"], 0)
        self.assertEqual(state["orders_sent"], 0)
        self.assertFalse(state["market_execution_authorized"])

    def test_partial_equity_can_research_m1_but_m2_m3_hold(self):
        state = decide(sample(include=(EQUITY,)))
        self.assertEqual(state["paper_candidates"], ["M1_GLOBAL_EQ"])
        self.assertEqual(state["model_states"]["M3_TACTICAL"]["status"], "HOLD_CASH")
        self.assertIn(GOLD, state["source_blockers"])

    def test_single_complete_snapshot_is_not_confirmed_m3(self):
        state = decide(sample())
        self.assertEqual(state["paper_candidates"], ["M1_GLOBAL_EQ", "M2_DIVERSIFIED"])
        m3 = state["model_states"]["M3_TACTICAL"]
        self.assertEqual(m3["reason"], "PREVIOUS_SNAPSHOT_MISSING")
        self.assertEqual(m3["virtual_target"], {"CASH_PLN": "1"})
        self.assertFalse(m3["previous_confirmation"])

    def test_two_consistent_consecutive_months_enable_m3_research_candidate(self):
        current, prev = pair()
        state = decide(current, prev)
        self.assertEqual(state["paper_candidates"],
                         ["M1_GLOBAL_EQ", "M2_DIVERSIFIED", "M3_TACTICAL"])
        m3 = state["model_states"]["M3_TACTICAL"]
        self.assertEqual(m3["reason"], "TWO_CONSECUTIVE_RESEARCH_SIGNALS")
        self.assertEqual(m3["raw_v05_signal"], "MOMENTUM_3M_RISK_ON")
        self.assertTrue(m3["previous_confirmation"])
        self.assertFalse(state["historical_point_in_time_certified"])
        self.assertFalse(state["investment_performance_proven"])

    def test_two_consecutive_risk_off_snapshots_can_be_studied(self):
        current, prev = pair(downward=True)
        state = decide(current, prev)
        m3 = state["model_states"]["M3_TACTICAL"]
        self.assertTrue(m3["previous_confirmation"])
        self.assertEqual(m3["raw_v05_signal"], "MOMENTUM_3M_RISK_OFF")
        self.assertEqual(m3["virtual_target"]["CASH_PLN"], "0.3")

    def test_transition_between_regimes_is_held_until_second_confirmation(self):
        current, prev = pair()
        current["series"][EQUITY]["observations"][-1]["level_pln"] = "400"
        state = decide(current, prev)
        m3 = state["model_states"]["M3_TACTICAL"]
        self.assertEqual(m3["reason"], "REGIME_CHANGE_AWAIT_CONFIRMATION")
        self.assertEqual(m3["status"], "HOLD_CASH")
        self.assertEqual(m3["virtual_target"], {"CASH_PLN": "1"})
        self.assertEqual(m3["raw_v05_signal"], "MOMENTUM_3M_RISK_OFF")

    def test_historical_revisions_never_silently_confirm_m3(self):
        current, prev = pair()
        current["series"][EQUITY]["observations"][20]["level_pln"] = "1250"
        m3 = decide(current, prev)["model_states"]["M3_TACTICAL"]
        self.assertEqual(m3["reason"], "HISTORICAL_OBSERVATIONS_REVISED_OR_MISSING")
        self.assertFalse(m3["previous_confirmation"])

    def test_nonconsecutive_months_are_blocked_for_m3(self):
        current, prev = pair()
        for asset in ASSETS:
            prev["series"][asset]["observations"].pop()
        m3 = decide(current, prev)["model_states"]["M3_TACTICAL"]
        self.assertEqual(m3["reason"], "NONCONSECUTIVE_MONTHLY_SNAPSHOTS")

    def test_old_source_rights_block_promotion(self):
        current, prev = pair()
        prev["series"][EQUITY]["rights_status"] = "UNVERIFIED"
        m3 = decide(current, prev)["model_states"]["M3_TACTICAL"]
        self.assertEqual(m3["reason"], "PREVIOUS_SOURCES_INELIGIBLE")

    def test_no_retroactive_or_same_month_decision_acceptance(self):
        current, prev = pair()
        prev["as_of_utc"] = current["as_of_utc"]
        with self.assertRaisesRegex(ShadowInputError, "precede current"):
            decide(current, prev)
        prev["as_of_utc"] = "2026-11-01T20:00:00+00:00"
        for source in prev["series"].values():
            source["retrieved_at"] = "2026-10-06T20:00:00+00:00"
        with self.assertRaisesRegex(ShadowInputError, "different decision month"):
            decide(current, prev)

    def test_rejects_live_trading_mode_in_both_inputs(self):
        current, prev = pair()
        current["mode"] = "LIVE_TRADING"
        with self.assertRaises(ShadowInputError):
            decide(current, prev)
        current, prev = pair()
        prev["mode"] = "LIVE_TRADING"
        with self.assertRaises(ShadowInputError):
            decide(current, prev)

    def test_no_fake_gold_from_price_only_source(self):
        current, prev = pair()
        current["series"][GOLD]["return_basis"] = "PRICE_ONLY"
        state = decide(current, prev)
        self.assertEqual(state["paper_candidates"], ["M1_GLOBAL_EQ"])
        self.assertIn("NOT_PLN_TOTAL_RETURN_BENCHMARK",
                      state["source_blockers"][GOLD])

    def test_deterministic_receipt_and_history_change_detection(self):
        current, prev = pair()
        self.assertEqual(decide(current, prev), decide(deepcopy(current), deepcopy(prev)))
        changed = deepcopy(current)
        changed["series"][EQUITY]["observations"][-1]["level_pln"] = "1400"
        self.assertNotEqual(decide(current, prev)["controller_receipt_sha256"],
                            decide(changed, prev)["controller_receipt_sha256"])

    def test_unchanged_source_documents_and_no_side_effects(self):
        current, prev = pair()
        before = deepcopy((current, prev))
        state = decide(current, prev)
        self.assertEqual((current, prev), before)
        for key in ("orders_sent", "paper_fills", "database_writes", "financial_operations"):
            self.assertEqual(state[key], 0)


if __name__ == "__main__":
    unittest.main()
