"""Synthetic-only independent source par-bond PV model checks."""
import math
import unittest

from scripts.swinkels_nine_independent_cashflow_pv_v01 import (
    SourceUnavailable, remaining_par_bond_monthly_return,
)


class IndependentRemainingBondCashflowTests(unittest.TestCase):
    def test_unchanged_yield_is_one_month_interest_accrual(self):
        self.assertAlmostEqual(
            remaining_par_bond_monthly_return(3.0, 3.0), 3.0 / 1200,
            places=12
        )

    def test_zero_yields_finite_and_zero_return(self):
        self.assertAlmostEqual(
            remaining_par_bond_monthly_return(0.0, 0.0), 0.0,
            places=14
        )

    def test_zero_current_yield_supported(self):
        result = remaining_par_bond_monthly_return(3.0, 0.0)
        self.assertTrue(math.isfinite(result))
        self.assertGreater(result, 0)

    def test_negative_yield_supported(self):
        result = remaining_par_bond_monthly_return(-0.3, -0.4)
        self.assertTrue(math.isfinite(result))

    def test_source_closed_form_equivalent_at_nonzero_yield(self):
        old, new = 3.0, 4.0
        x = (1 + new / 200) ** (-2 * (10 - 1/12))
        source_equivalent = old / 1200 + (old/new) * (1-x) + x - 1
        self.assertAlmostEqual(
            remaining_par_bond_monthly_return(old, new),
            source_equivalent,
            places=12
        )

    def test_increasing_yield_reduces_return(self):
        lower = remaining_par_bond_monthly_return(3.0, 2.0)
        higher = remaining_par_bond_monthly_return(3.0, 4.0)
        self.assertGreater(lower, higher)

    def test_invalid_nan_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "invalid"):
            remaining_par_bond_monthly_return(float("nan"), 3.0)

    def test_invalid_infinite_yield_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "invalid"):
            remaining_par_bond_monthly_return(3.0, float("inf"))

    def test_extreme_yield_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "invalid"):
            remaining_par_bond_monthly_return(3.0, 120.0)

    def test_no_discretionary_magnitude_conversion(self):
        # Inputs here are explicitly percent points, not ODF fractional yields.
        old, new = 4.0, 5.0
        raw_correct = remaining_par_bond_monthly_return(old, new)
        wrong_unit = remaining_par_bond_monthly_return(old/100, new/100)
        self.assertGreater(abs(raw_correct - wrong_unit), 1e-4)


if __name__ == "__main__":
    unittest.main()
