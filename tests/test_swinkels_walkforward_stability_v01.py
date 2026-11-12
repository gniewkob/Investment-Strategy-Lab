"""Offline, synthetic-only negative tests for lag and source gates."""
import math
import unittest

from scripts.research_swinkels_original_source_probe_v01 import SourceUnavailable
from scripts.swinkels_walkforward_stability_v01 import (
    _predictions_before, evaluate_lagged_error, source_bound_diagnostic,
)


class WalkForwardDiagnosticsTests(unittest.TestCase):
    def test_fixed_window_and_bounds(self):
        report = evaluate_lagged_error([0.01] * 36)
        self.assertEqual(report["evaluation_months"], 24)
        self.assertEqual(report["evaluation_first_month"], "2021-01")
        self.assertEqual(report["evaluation_last_month"], "2022-12")
        self.assertEqual(report["candidate_lower_error_months"], 0)
        self.assertEqual(report["baseline_mae_bps"], "0.0000")
        self.assertEqual(report["candidate_mae_bps"], "0.0000")
        self.assertFalse(report["historical_pit_certified"])
        self.assertTrue(report["not_investment_performance"])

    def test_target_current_return_cannot_leak_into_forecast(self):
        original = [0.01] * 36
        for i in range(12, 36):
            modified = original.copy()
            modified[i] = 0.8
            self.assertEqual(
                _predictions_before(tuple(original), i),
                _predictions_before(tuple(modified), i),
            )

    def test_later_month_cannot_change_earlier_prediction(self):
        data = [0.01] * 36
        expected = _predictions_before(tuple(data), 18)
        data[19] = 0.8
        self.assertEqual(_predictions_before(tuple(data), 18), expected)

    def test_prior_month_does_change_candidate(self):
        data = [0.01] * 36
        initial = _predictions_before(tuple(data), 18)
        data[17] = 0.04
        final = _predictions_before(tuple(data), 18)
        self.assertAlmostEqual(final[1] - initial[1], 0.03 / 6)

    def test_trailing_six_excludes_present_month(self):
        data = [0] * 36
        for i in range(6, 12):
            data[i] = 0.03
        data[12] = 0.9
        self.assertAlmostEqual(_predictions_before(tuple(data), 12)[1], 0.03)
        self.assertAlmostEqual(_predictions_before(tuple(data), 12)[0], 0.015)

    def test_reject_missing_extra_or_unstructured_months(self):
        for data in ([], [0.01] * 35, [0.01] * 37, None, {}):
            with self.assertRaisesRegex(SourceUnavailable, "FORECAST_WINDOW"):
                evaluate_lagged_error(data)

    def test_reject_nonfinite_bool_and_invalid_returns(self):
        for bad in (True, float("nan"), float("inf"), -1.0, -1.1, "0.1"):
            data = [0.01] * 36
            data[16] = bad
            with self.subTest(value=str(bad)), self.assertRaisesRegex(
                SourceUnavailable, "FORECAST_RETURN"
            ):
                evaluate_lagged_error(data)

    def test_reject_invalid_prediction_index(self):
        for invalid in (-1, 0, 11, 36, True, "12"):
            with self.assertRaisesRegex(SourceUnavailable, "FORECAST_TARGET"):
                _predictions_before(tuple([0.01] * 36), invalid)

    def test_aggregate_not_financial_or_alpha_claim(self):
        data = tuple(0.005 + 0.002 * math.sin(i) for i in range(36))
        result = evaluate_lagged_error(data)
        self.assertEqual(result["evaluation_months"], 24)
        self.assertTrue(result["not_investment_performance"])
        self.assertFalse(result["confirmatory_holdout"])
        self.assertNotIn("orders", result)
        self.assertNotIn("actual_profit", result)

    def test_unverified_source_bytes_cannot_pass(self):
        for bad in (None, "", b"", b"made-up-data"):
            with self.assertRaisesRegex(SourceUnavailable, "ORIGINAL_ODS_SHA"):
                source_bound_diagnostic(bad)


if __name__ == "__main__":
    unittest.main()
