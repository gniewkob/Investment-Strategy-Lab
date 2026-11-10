"""Synthetic-only tests of the independent nine-variant Eq3 research diagnostic."""
import math
import unittest

from scripts.swinkels_nine_equation3_diagnostic_v01 import (
    MONTHS, SOURCE_WINDOW, SHEETS, SourceUnavailable, compare_series, diagnostic,
)


def fake_source(yield_points=3.0):
    carry = (1 + yield_points / 100) ** (1 / 12) - 1
    return {
        month: {
            "yield_points": yield_points,
            "return_fraction": carry,
        }
        for month in SOURCE_WINDOW
    }


class NineSeriesEquation3Tests(unittest.TestCase):
    def test_constant_yield_equation3(self):
        summary = compare_series(fake_source())
        self.assertEqual(summary["months"], 36)
        self.assertEqual(float(summary["max_abs_gap_compound_carry"]), 0.0)
        self.assertEqual(summary["independent_economic_reproduction"], "DIAGNOSTIC_ONLY")

    def test_year_month_research_scope(self):
        self.assertEqual(len(MONTHS), 36)
        self.assertEqual(len(SOURCE_WINDOW), 37)
        self.assertEqual(len(SHEETS), 9)

    def test_nonzero_simple_vs_compounded_carry_difference(self):
        result = compare_series(fake_source(6.0))
        self.assertGreater(float(result["rms_gap_simple_carry"]), 0)

    def test_missing_month_rejected(self):
        rows = fake_source()
        del rows["2020-01"]
        with self.assertRaisesRegex(SourceUnavailable, "window"):
            compare_series(rows)

    def test_unqualified_nine_series(self):
        payload = diagnostic({name: fake_source() for name in SHEETS})
        self.assertEqual(payload["country_variant_count"], 9)
        self.assertFalse(payload["formula_economic_semantics_certified"])
        self.assertFalse(payload["historical_pit_certified"])
        self.assertEqual(payload["qualified_model_series"], [])
        self.assertEqual(payload["model_state"], "HOLD_CASH")
        self.assertEqual(payload["financial_operations"], 0)

    def test_missing_country_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "incomplete"):
            diagnostic({SHEETS[0]: fake_source()})

    def test_nonfinite_return_rejected(self):
        source = fake_source()
        source["2021-01"]["return_fraction"] = float("nan")
        with self.assertRaisesRegex(SourceUnavailable, "nonfinite"):
            compare_series(source)


if __name__ == "__main__":
    unittest.main()
