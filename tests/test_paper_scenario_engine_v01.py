"""Deterministic offline tests, using synthetic price observations only."""
from decimal import Decimal
import unittest
from scripts.paper_scenario_engine_v01 import run_scenario, ScenarioBlocked


def sample(prices=("10", "20", "20")):
    return [{"month": f"2026-{i:02d}", "available_month": f"2026-{i:02d}",
             "price_pln": p} for i, p in enumerate(prices, 1)]


class PaperScenarioEngineTests(unittest.TestCase):
    def test_asset_contributions_and_mark_to_market(self):
        result = run_scenario(observations=sample())
        self.assertEqual(Decimal(result["ending_value_pln"]), Decimal("400"))
        self.assertEqual(result["contributions_pln"], "300")
        self.assertEqual(Decimal(result["difference_vs_cash_pln"]), Decimal("100"))
        self.assertEqual(result["orders_sent"], 0)
        self.assertFalse(result["model_admitted"])

    def test_cash_baseline_ignores_market(self):
        result = run_scenario(observations=sample(), mode="cash")
        self.assertEqual(result["ending_value_pln"], "300")
        self.assertEqual(result["total_fees_pln"], "0")

    def test_costs_are_deducted_before_fractional_purchase(self):
        result = run_scenario(observations=sample(("10", "10", "10")), fee_fixed_pln="1", fee_rate="0.01")
        self.assertEqual(Decimal(result["ending_value_pln"]), Decimal("294"))
        self.assertEqual(Decimal(result["total_fees_pln"]), Decimal("6.00"))

    def test_one_month_exact_mark(self):
        result = run_scenario(observations=sample(("2",)))
        self.assertEqual(result["ending_value_pln"], "100")

    def test_unavailable_future_price_rejected(self):
        rows = sample()
        rows[0]["available_month"] = "2026-02"
        with self.assertRaisesRegex(ScenarioBlocked, "LOOK_AHEAD"):
            run_scenario(observations=rows)

    def test_missing_and_duplicate_month_rejected(self):
        for rows in (sample()[:1] + sample()[2:], sample()[:2] + sample()[1:2]):
            with self.subTest(rows=rows), self.assertRaisesRegex(ScenarioBlocked, "NONCONTIGUOUS"):
                run_scenario(observations=rows)

    def test_nan_boolean_and_negative_values_rejected(self):
        for bad in ("NaN", "Infinity", "-4", True, 1.1):
            rows = sample()
            rows[0]["price_pln"] = bad
            with self.subTest(bad=bad), self.assertRaises(ScenarioBlocked):
                run_scenario(observations=rows)

    def test_fees_cannot_use_more_than_contribution(self):
        with self.assertRaises(ScenarioBlocked):
            run_scenario(observations=sample(), fee_fixed_pln="100")

    def test_no_network_or_persistence(self):
        import socket
        original = socket.socket.connect
        try:
            socket.socket.connect = lambda *_: (_ for _ in ()).throw(AssertionError("network"))
            result = run_scenario(observations=sample())
            self.assertEqual(result["database_writes"], 0)
        finally:
            socket.socket.connect = original


if __name__ == "__main__":
    unittest.main()
