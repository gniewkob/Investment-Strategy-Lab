"""Synthetic-only ODF yield-unit classification tests."""
import unittest

from scripts.swinkels_nine_variant_yield_unit_census_v01 import storage_semantics


class NineVariantSourceUnitTests(unittest.TestCase):
    def test_percent_fraction_is_explicit(self):
        self.assertEqual(
            storage_semantics("percentage", "percentage-style"),
            "ODF_PERCENT_FRACTION"
        )

    def test_generic_float_does_not_certify_scale(self):
        self.assertEqual(
            storage_semantics("float", "number-style"),
            "GENERIC_FLOAT_SCALE_NOT_CERTIFIED"
        )

    def test_percentage_type_with_nonpercentage_display_requires_review(self):
        self.assertEqual(
            storage_semantics("percentage", "number-style"),
            "STORAGE_SEMANTICS_REVIEW_REQUIRED"
        )

    def test_float_with_percentage_display_requires_review(self):
        self.assertEqual(
            storage_semantics("float", "percentage-style"),
            "STORAGE_SEMANTICS_REVIEW_REQUIRED"
        )

    def test_missing_style_requires_review(self):
        self.assertEqual(
            storage_semantics("float", "UNRESOLVED"),
            "STORAGE_SEMANTICS_REVIEW_REQUIRED"
        )

    def test_currency_is_not_a_yield(self):
        self.assertEqual(
            storage_semantics("currency", "currency-style"),
            "STORAGE_SEMANTICS_REVIEW_REQUIRED"
        )


if __name__ == "__main__":
    unittest.main()
