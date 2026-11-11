"""Acceptance of v0.14 frozen educational-only cost scenarios."""
from copy import deepcopy
from decimal import Decimal
import unittest

from scripts.monthly_cost_sensitivity_v14 import analyze
from scripts.monthly_proxy_backtest_v04 import BacktestValidationError, MODELS
from tests.test_monthly_proxy_backtest_v04 import fixture


class CostSensitivityV14Tests(unittest.TestCase):
    def test_synthetic_three_models_all_scenarios_and_no_real_operations(self):
        result = analyze(fixture(n=60, train=36))
        self.assertEqual(result["status"], "SENSITIVITY_SYNTHETIC_TEST_ONLY")
        self.assertEqual(result["scenario_count"], 4)
        self.assertEqual(len(result["scenarios"]), 4)
        self.assertEqual([x["scenario"] for x in result["scenarios"]],
                         ["ZERO", "BASE_20_10", "HIGH_50_50", "STRESS_100_100"])
        for row in result["scenarios"]:
            self.assertEqual(set(row["models"]), set(MODELS))
            self.assertEqual(row["run_status"], "SYNTHETIC_TEST_ONLY")
        for model in MODELS:
            self.assertGreaterEqual(
                Decimal(result["model_cost_exposure"][model]["zero_cost_minus_stress_reference_pln"]),
                Decimal("0"))
        self.assertEqual(result["real_orders"], 0)
        self.assertEqual(result["paper_events_created"], 0)
        self.assertEqual(result["database_connections"], 0)
        self.assertEqual(result["database_writes"], 0)
        self.assertFalse(result["investment_performance_proven"])
        self.assertFalse(result["statistical_edge_proven"])

    def test_repeated_runs_are_bit_for_bit_deterministic(self):
        data = fixture()
        self.assertEqual(analyze(data), analyze(deepcopy(data)))

    def test_no_cost_sweep_can_create_returns_from_missing_required_series(self):
        data = fixture()
        data["series"].pop("GLOBAL_EQUITY_TR_PLN")
        result = analyze(data)
        self.assertEqual(result["status"], "NOT_RUN_SOURCE_OR_HISTORY_BLOCKED")
        self.assertEqual(result["missing_required_series"], ["GLOBAL_EQUITY_TR_PLN"])
        self.assertTrue(all(not s["models"] for s in result["scenarios"]))
        self.assertEqual(result["model_cost_exposure"], {})

    def test_short_historical_reconstruction_does_not_generate_performance(self):
        data = fixture()
        data["source_vintage"] = "HISTORICAL_RESEARCH_RECONSTRUCTION"
        result = analyze(data)
        self.assertEqual(result["status"], "NOT_RUN_SOURCE_OR_HISTORY_BLOCKED")
        self.assertEqual(result["underlying_status"], "NOT_RUN_INSUFFICIENT_HISTORY")
        self.assertEqual(result["available_months"], 18)
        self.assertTrue(all(not r["models"] for r in result["scenarios"]))

    def test_historical_reconstruction_remains_conditional_and_uncertified(self):
        data = fixture(n=48, train=30, start_year=2022)
        data["source_vintage"] = "HISTORICAL_RESEARCH_RECONSTRUCTION"
        result = analyze(data)
        self.assertEqual(result["status"], "SENSITIVITY_CONDITIONAL_HISTORICAL_RECONSTRUCTION")
        self.assertFalse(result["historical_pit_certified"])
        self.assertFalse(result["investment_performance_proven"])
        self.assertFalse(result["parameters_optimized"])

    def test_rejects_live_mode(self):
        data = fixture()
        data["mode"] = "LIVE_TRADING"
        with self.assertRaises(BacktestValidationError):
            analyze(data)

    def test_rejects_false_point_in_time_certification(self):
        data = fixture()
        data["historical_pit_certified"] = True
        with self.assertRaises(BacktestValidationError):
            analyze(data)

    def test_does_not_hide_invalid_original_costs_by_overwriting_them(self):
        data = fixture(fee="999")
        with self.assertRaises(BacktestValidationError):
            analyze(data)

    def test_rejects_price_only_gold_and_non_pln_bonds(self):
        for key, field, value in (
            ("GOLD_TR_PLN", "return_basis", "PRICE_ONLY"),
            ("PL_BONDS_TR_PLN", "quote_currency", "USD"),
        ):
            data = fixture()
            data["series"][key][field] = value
            with self.subTest(key=key), self.assertRaises(BacktestValidationError):
                analyze(data)

    def test_change_in_reference_prices_changes_fingerprints(self):
        data = fixture()
        changed = deepcopy(data)
        changed["series"]["PL_BONDS_TR_PLN"]["rows"][-1]["level_pln"] = "250"
        self.assertNotEqual(analyze(data)["receipt_sha256"],
                            analyze(changed)["receipt_sha256"])

    def test_sensitivity_does_not_mutate_source_document(self):
        data = fixture()
        before = deepcopy(data)
        analyze(data)
        self.assertEqual(data, before)


if __name__ == "__main__":
    unittest.main()
