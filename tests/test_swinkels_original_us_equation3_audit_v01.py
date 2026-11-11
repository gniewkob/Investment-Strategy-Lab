"""Synthetic-only independent Swinkels Eq.3 and duration/convexity tests."""
import math
import unittest

from scripts.swinkels_original_us_equation3_audit_v01 import (
    ALL_MONTHS, MONTHS, SourceUnavailable,
    par_bond_sensitivities, equation3, reconcile, summarize_monthly_returns,
)


class IndependentBondMathTests(unittest.TestCase):
    def test_par_bond_duration_matches_author_equation_1(self):
        for annual_yield in (0.01, 0.03, 0.08):
            duration, _ = par_bond_sensitivities(annual_yield)
            closed_form = (1 - (1 + annual_yield / 2) ** (-20)) / annual_yield
            self.assertAlmostEqual(duration, closed_form, places=11)

    def test_convexity_is_positive(self):
        _, convexity = par_bond_sensitivities(0.03)
        self.assertGreater(convexity, 0)

    def test_constant_yield_is_monthly_carry(self):
        duration, convexity = par_bond_sensitivities(0.03)
        expected = (1.03) ** (1 / 12) - 1
        self.assertAlmostEqual(equation3(0.03, 0.03, duration, convexity), expected, places=13)

    def test_higher_yield_reduces_return(self):
        duration, convexity = par_bond_sensitivities(0.03)
        stable = equation3(0.03, 0.03, duration, convexity)
        higher = equation3(0.03, 0.031, duration, convexity)
        self.assertLess(higher, stable)

    def test_synthetic_source_reconciles_without_market_data(self):
        annual_yield = 0.03
        duration, convexity = par_bond_sensitivities(annual_yield)
        carry = (1 + annual_yield) ** (1 / 12) - 1
        records = {
            month: dict(yield_=annual_yield, duration=duration, convexity=convexity, return_=carry)
            for month in ALL_MONTHS
        }
        records = {
            month: {"yield": row["yield_"], "duration": row["duration"],
                    "convexity": row["convexity"], "return": row["return_"]}
            for month, row in records.items()
        }
        result = reconcile(records)
        self.assertEqual(result["months_reconciled"], len(MONTHS))
        self.assertEqual(float(result["max_abs_return_gap_using_independent_duration_convexity"]), 0)
        self.assertEqual(result["qualified_model_series"], [])
        self.assertEqual(result["financial_operations"], 0)
        self.assertEqual(result["model_state"], "HOLD_CASH")

    def test_synthetic_aggregate_statistics(self):
        result = summarize_monthly_returns([0.01] * 36)
        self.assertEqual(result["observations"], 36)
        self.assertAlmostEqual(
            float(result["compounded_total_return_pct"]),
            100 * ((1.01 ** 36) - 1), places=3)
        self.assertEqual(float(result["max_drawdown_pct"]), 0)
        self.assertEqual(result["research_only"], True)
        self.assertEqual(result["historical_pit_certified"], False)

    def test_synthetic_drawdown_statistic(self):
        result = summarize_monthly_returns([-0.10] + [0.0] * 35)
        self.assertAlmostEqual(float(result["max_drawdown_pct"]), -10, places=6)

    def test_statistic_rejects_missing_observation(self):
        with self.assertRaisesRegex(SourceUnavailable, "invalid statistical"):
            summarize_monthly_returns([0.0] * 35)

    def test_missing_month_blocks_reconciliation(self):
        with self.assertRaisesRegex(SourceUnavailable, "window mismatch"):
            reconcile({})

    def test_nonfinite_yield_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "invalid yield"):
            par_bond_sensitivities(float("nan"))

    def test_nonfinite_equation3_input_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "non-finite"):
            equation3(0.02, float("inf"), 9.0, 50.0)


if __name__ == "__main__":
    unittest.main()
