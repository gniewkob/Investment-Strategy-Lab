"""I4: negative admission tests for A1 -> C1 boundary; synthetic only."""
from __future__ import annotations

from copy import deepcopy
import unittest

from scripts.monthly_proxy_backtest_v04 import run_backtest
from scripts.research_backtest_decision_boundary_v01 import (
    BacktestBoundaryError, review_backtest, SCHEMA, RESEARCH_REASONS,
)
from scripts.research_decision_pipeline_v16 import run_cycle
from scripts.shadow_decision_engine_v05 import ShadowInputError
from tests.test_monthly_proxy_backtest_v04 import fixture
from tests.test_shadow_decision_engine_v05 import sample


class A1C1DecisionFirewallTests(unittest.TestCase):
    @staticmethod
    def synthetic():
        return run_backtest(fixture(n=18, train=10))

    @staticmethod
    def historical():
        p = fixture(n=48, train=30, start_year=2022)
        p["source_vintage"] = "HISTORICAL_RESEARCH_RECONSTRUCTION"
        return run_backtest(p)

    def assert_holds(self, report):
        result = run_cycle(backtest_report=report)
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["status"], "HOLD_CASH_BACKTEST_NOT_QUALIFIED_SOURCE")
        self.assertEqual(result["input_kind"], "A1_NON_EXECUTABLE_RESEARCH_REPORT")
        self.assertEqual(result["paper_candidates"], [])
        self.assertEqual(len(result["model_decisions"]), 3)
        self.assertTrue(all(state["status"] == "HOLD_CASH"
                            and state["virtual_target"] == {"CASH_PLN": "1"}
                            for state in result["model_decisions"].values()))
        self.assertEqual(tuple(result["research_blockers"]), RESEARCH_REASONS)
        self.assertFalse(result["historical_pit_certified"])
        self.assertFalse(result["source_rights_independently_certified"])
        self.assertFalse(result["investment_performance_proven"])
        self.assertFalse(result["source_manifest_created"])
        self.assertFalse(result["real_order_authorized"])
        self.assertFalse(result["integration_to_main_authorized"])
        for name in ("orders_sent", "paper_fills",
                     "financial_operations", "database_writes"):
            self.assertEqual(result[name], 0)
        self.assertRegex(result["boundary_receipt_sha256"], r"^[0-9a-f]{64}$")
        return result

    def test_synthetic_success_never_becomes_decision_source(self):
        report = self.synthetic()
        self.assertEqual(report["status"], "SYNTHETIC_TEST_ONLY")
        self.assert_holds(report)

    def test_high_hypothetical_return_does_not_override_source_gate(self):
        report = self.synthetic()
        for model in report["results"]:
            model["flow_adjusted_twr_pct"] = "999999.00"
        self.assert_holds(report)

    def test_historical_reconstruction_still_has_no_pit_proof(self):
        report = self.historical()
        self.assertEqual(report["status"], "CONDITIONAL_HISTORICAL_RECONSTRUCTION")
        self.assert_holds(report)

    def test_missing_source_report_still_stays_hold(self):
        p = fixture()
        del p["series"]["GOLD_TR_PLN"]
        report = run_backtest(p)
        self.assertEqual(report["status"], "NOT_RUN_INSUFFICIENT_DATA")
        self.assert_holds(report)

    def test_short_history_reconstruction_stays_hold(self):
        p = fixture()
        p["source_vintage"] = "HISTORICAL_RESEARCH_RECONSTRUCTION"
        report = run_backtest(p)
        self.assertEqual(report["status"], "NOT_RUN_INSUFFICIENT_HISTORY")
        self.assert_holds(report)

    def test_pit_or_performance_claims_are_refused(self):
        for key in ("historical_pit_certified", "investment_performance_proven"):
            report = self.synthetic()
            report[key] = True
            with self.subTest(key=key), self.assertRaises(BacktestBoundaryError):
                review_backtest(report)

    def test_report_with_financial_or_db_activity_is_refused(self):
        for key in ("real_orders", "paper_events_created",
                    "database_connections", "database_writes"):
            report = self.synthetic()
            report[key] = 1
            with self.subTest(key=key), self.assertRaisesRegex(
                    BacktestBoundaryError, "activity claimed"):
                review_backtest(report)

    def test_bool_false_masquerading_as_zero_does_not_pass(self):
        report = self.synthetic()
        report["real_orders"] = False
        with self.assertRaises(BacktestBoundaryError):
            review_backtest(report)

    def test_extra_promotion_contract_fields_are_rejected(self):
        for key, value in (("paper_candidates", ["M1_GLOBAL_EQ"]),
                           ("source_status", "VERIFIED_ORIGINAL"),
                           ("market_execution_authorized", True),
                           ("rights_status", "RESEARCH_USE_DOCUMENTED")):
            report = self.synthetic()
            report[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(
                    BacktestBoundaryError, "promotion fields"):
                review_backtest(report)

    def test_foreign_or_forged_status_rejected(self):
        for status in ("PAPER_CANDIDATE_ONLY", "LIVE_TRADING",
                       "QUALIFIED_REAL_MARKET", "", None):
            report = self.synthetic()
            report["status"] = status
            with self.subTest(status=status), self.assertRaises(BacktestBoundaryError):
                review_backtest(report)

    def test_vintage_mismatch_is_rejected(self):
        report = self.synthetic()
        report["source_vintage"] = "HISTORICAL_RESEARCH_RECONSTRUCTION"
        with self.assertRaisesRegex(BacktestBoundaryError, "contradictory"):
            review_backtest(report)

    def test_modified_model_identity_or_additional_execution_flag_rejected(self):
        for key, value in (("model_code", "REAL_ORDERS"),
                           ("execution_authorized", True)):
            report = self.synthetic()
            report["results"][0][key] = value
            with self.subTest(key=key), self.assertRaises(BacktestBoundaryError):
                review_backtest(report)

    def test_partial_or_modified_timeline_rejected(self):
        report = self.synthetic()
        report["results"][0]["timeline"].pop()
        with self.assertRaisesRegex(BacktestBoundaryError, "timeline"):
            review_backtest(report)
        report = self.synthetic()
        report["results"][0]["timeline"][0]["source_qualified"] = True
        with self.assertRaisesRegex(BacktestBoundaryError, "timeline"):
            review_backtest(report)

    def test_pipeline_refuses_mixing_backtest_with_source_or_archive(self):
        report = self.synthetic()
        for options in ({"current": sample(include=())},
                        {"previous": sample(include=())},
                        {"archived_bundle": {}}):
            with self.subTest(keys=tuple(options)), self.assertRaisesRegex(
                    ShadowInputError, "cannot be combined"):
                run_cycle(backtest_report=report, **options)

    def test_raw_backtest_cannot_be_disguised_as_current_c1_manifest(self):
        report = self.synthetic()
        with self.assertRaises(ShadowInputError):
            run_cycle(current=report)

    def test_explicit_c1_empty_manifest_route_unchanged(self):
        out = run_cycle(current=sample(include=()))
        self.assertEqual(out["status"], "HOLD_CASH_SOURCE_OR_CONFIRMATION_BLOCKED")
        self.assertEqual(out["paper_candidates"], [])

    def test_report_unchanged_and_receipt_is_deterministic(self):
        report = self.synthetic()
        original = deepcopy(report)
        first = self.assert_holds(report)
        second = self.assert_holds(deepcopy(report))
        self.assertEqual(report, original)
        self.assertEqual(first, second)

    def test_unrepresentable_nan_report_rejected(self):
        report = self.synthetic()
        report["results"][0]["flow_adjusted_twr_pct"] = float("nan")
        with self.assertRaisesRegex(BacktestBoundaryError, "canonical JSON"):
            review_backtest(report)


if __name__ == "__main__":
    unittest.main()
