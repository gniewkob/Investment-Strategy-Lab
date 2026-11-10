"""Synthetic-only tests for the Swinkels offline research gate."""
import unittest
from decimal import Decimal

from scripts.swinkels_offline_research_gate_v01 import (
    EXPECTED_MONTHS, SOURCE_SHA256, ResearchGateBlocked,
    validate_monthly_series, offline_statistics,
)


def example_rows():
    return [(m, "0.01") for m in EXPECTED_MONTHS]


def accepted(**overrides):
    args = dict(
        country="DE",
        observations=example_rows(),
        source_sha256=SOURCE_SHA256,
        return_unit="decimal",
        unit_evidence="human-reviewed-source-reference-required",
        methodology_evidence="Swinkels 2019 sections 2-3",
    )
    args.update(overrides)
    return validate_monthly_series(**args)


class TestSwinkelsGate(unittest.TestCase):
    def assert_blocked(self, expected, **kwargs):
        with self.assertRaisesRegex(ResearchGateBlocked, expected):
            accepted(**kwargs)

    def test_complete_decimal(self):
        self.assertEqual(accepted(), (Decimal("0.01"),) * 36)

    def test_explicit_percent_conversion(self):
        rows = [(m, "1") for m in EXPECTED_MONTHS]
        self.assertEqual(accepted(observations=rows, return_unit="percent"), (Decimal("0.01"),) * 36)

    def test_missing_unit(self):
        self.assert_blocked("RETURN_UNITS_UNVERIFIED", return_unit=None)

    def test_guess_unit_not_allowed(self):
        self.assert_blocked("RETURN_UNITS_UNVERIFIED", return_unit="auto")

    def test_missing_unit_evidence(self):
        self.assert_blocked("RETURN_UNIT_EVIDENCE_MISSING", unit_evidence=None)

    def test_missing_methodology_evidence(self):
        self.assert_blocked("METHODOLOGY_EVIDENCE_MISSING", methodology_evidence="")

    def test_wrong_hash(self):
        self.assert_blocked("SOURCE_HASH_MISMATCH", source_sha256="a" * 64)

    def test_wrong_country(self):
        self.assert_blocked("COUNTRY_OR_VARIANT_NOT_SUPPORTED", country="PL")

    def test_missing_month(self):
        self.assert_blocked("MONTHLY_COVERAGE_INCOMPLETE", observations=example_rows()[:-1])

    def test_duplicate_month(self):
        rows = example_rows()
        rows[1] = rows[0]
        self.assert_blocked("DUPLICATE_MONTH", observations=rows)

    def test_out_of_window_month(self):
        rows = example_rows()
        rows[0] = ("2023-01", "0.01")
        self.assert_blocked("MONTHLY_WINDOW_MISMATCH", observations=rows)

    def test_nan(self):
        rows = example_rows()
        rows[0] = (rows[0][0], "NaN")
        self.assert_blocked("NONFINITE_RETURN_VALUE", observations=rows)

    def test_infinity(self):
        rows = example_rows()
        rows[0] = (rows[0][0], "Infinity")
        self.assert_blocked("NONFINITE_RETURN_VALUE", observations=rows)

    def test_bool_not_number(self):
        rows = example_rows()
        rows[0] = (rows[0][0], True)
        self.assert_blocked("INVALID_RETURN_VALUE", observations=rows)

    def test_below_minus_100_percent(self):
        rows = example_rows()
        rows[0] = (rows[0][0], "-1")
        self.assert_blocked("RETURN_AT_OR_BELOW_MINUS_100_PERCENT", observations=rows)

    def test_invalid_month(self):
        rows = example_rows()
        rows[0] = ("2020-13", "0.01")
        self.assert_blocked("INVALID_MONTH", observations=rows)

    def test_no_statistics_on_unvalidated_data(self):
        with self.assertRaisesRegex(ResearchGateBlocked, "UNVALIDATED_MONTHLY_SERIES"):
            offline_statistics([Decimal("0.01")] * 36)

    def test_synthetic_statistics(self):
        receipt = offline_statistics(accepted())
        self.assertEqual(receipt["sample_months"], 36)
        self.assertEqual(receipt["compounded_total_return"], Decimal("1.01") ** 36 - 1)
        self.assertEqual(receipt["max_drawdown"], Decimal(0))
        self.assertEqual(receipt["model_state"], "HOLD_CASH")
        self.assertEqual(receipt["qualified_model_series"], [])
        self.assertFalse(receipt["historical_pit_certified"])


if __name__ == "__main__":
    unittest.main()
