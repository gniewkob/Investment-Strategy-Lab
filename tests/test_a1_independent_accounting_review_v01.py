"""A1 independent synthetic accounting invariants, beyond the original v0.4 tests.

No live data, tradable quotes, DB, network, brokerage or wallet operations.
All observed results remain NON_EXECUTABLE benchmark-proxy research.
"""
from copy import deepcopy
from decimal import Decimal
import unittest

from scripts.monthly_proxy_backtest_v04 import ASSETS, run_backtest
from tests.test_monthly_proxy_backtest_v04 import fixture


class A1IndependentAccountingReviewTests(unittest.TestCase):
    def test_flat_price_zero_cost_has_no_fabricated_investment_return(self):
        data = fixture(n=18, train=10, fee="0", slip="0")
        for asset in ASSETS:
            for row in data["series"][asset]["rows"]:
                row["level_pln"] = "100"
        result = run_backtest(data)
        self.assertEqual(result["status"], "SYNTHETIC_TEST_ONLY")
        for model in result["results"]:
            with self.subTest(model=model["model_code"]):
                self.assertEqual(model["end_reference_value_pln"], "1800.00")
                self.assertEqual(model["net_reference_pnl_pln"], "0.00")
                self.assertEqual(model["flow_adjusted_twr_pct"], "0.0000")
                self.assertEqual(model["flow_adjusted_max_drawdown_pct"], "0.0000")
                self.assertEqual(model["assumed_fees_pln"], "0.00")
                self.assertEqual(model["assumed_slippage_pln"], "0.00")

    def test_m1_zero_cost_twr_matches_index_ratio_not_dca_roi(self):
        data = fixture(n=18, train=10, fee="0", slip="0")
        result = run_backtest(data)["results"][0]
        prices = [Decimal(row["level_pln"]) for row in
                  data["series"]["GLOBAL_EQUITY_TR_PLN"]["rows"]]
        index_twr_pct = (prices[-1] / prices[0] - 1) * Decimal(100)
        reported = Decimal(result["flow_adjusted_twr_pct"])
        self.assertLess(abs(reported - index_twr_pct), Decimal("0.0001"))
        self.assertNotEqual(result["flow_adjusted_twr_pct"],
                            result["simple_contribution_roi_pct"])
        self.assertEqual(result["contributed_pln"], "1800.00")

    def test_reported_in_and_out_of_sample_returns_recompose_total_twr(self):
        result = run_backtest(fixture(n=60, train=36, fee="20", slip="10"))
        for model in result["results"]:
            train = Decimal(model["in_sample_twr_pct"])
            test = Decimal(model["out_of_sample_twr_pct"])
            whole = Decimal(model["flow_adjusted_twr_pct"])
            recomposed = ((1 + train / 100) * (1 + test / 100) - 1) * 100
            with self.subTest(model=model["model_code"]):
                self.assertLess(abs(recomposed - whole), Decimal("0.0002"))

    def test_flat_price_costs_are_expenses_not_market_return(self):
        data = fixture(n=18, train=10, fee="50", slip="20")
        for asset in ASSETS:
            for row in data["series"][asset]["rows"]:
                row["level_pln"] = "100"
        result = run_backtest(data)
        for model in result["results"]:
            pnl = Decimal(model["net_reference_pnl_pln"])
            fees = Decimal(model["assumed_fees_pln"])
            slip = Decimal(model["assumed_slippage_pln"])
            with self.subTest(model=model["model_code"]):
                self.assertLessEqual(pnl, 0)
                self.assertLess(abs(pnl + fees + slip), Decimal("0.03"))

    def test_mutating_future_observation_cannot_rewrite_prior_portfolio_path(self):
        original = fixture(n=18, train=10)
        changed = deepcopy(original)
        changed["series"]["GLOBAL_EQUITY_TR_PLN"]["rows"][-1]["level_pln"] = "10"
        first = run_backtest(original)
        second = run_backtest(changed)
        self.assertNotEqual(first["input_sha256"], second["input_sha256"])
        for a, b in zip(first["results"], second["results"]):
            with self.subTest(model=a["model_code"]):
                self.assertEqual(a["timeline"][:-1], b["timeline"][:-1])
                self.assertNotEqual(a["timeline"][-1]["portfolio_reference_value_pln"],
                                    b["timeline"][-1]["portfolio_reference_value_pln"])


if __name__ == "__main__":
    unittest.main()
