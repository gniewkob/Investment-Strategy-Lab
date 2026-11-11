"""Synthetic-only negative tests for SHA-pinned original Swinkels receipt.

Mocks never act as original publisher proof: actual source admission is checked
by separate official-dataverse HTTPS CI, pinned SHA and both independent models.
"""
from hashlib import sha256
from unittest.mock import patch
import unittest

from scripts import swinkels_source_bound_stats_v01 as s
from scripts.research_swinkels_original_source_probe_v01 import SourceUnavailable
from scripts.swinkels_nine_equation3_diagnostic_v01 import SHEETS

FAKE = b"synthetic fixture, NOT an ODS"


def stats():
    return {
        "observations": 36,
        "data_window": "2020-01..2022-12",
        "compounded_total_return_pct": "-1.000",
        "mean_monthly_return_pct": "-0.028",
        "monthly_sample_volatility_pct": "0.500",
        "max_drawdown_pct": "-1.500",
        "research_only": True,
        "historical_pit_certified": False,
        "costs_taxes_currency_translation_included": False,
    }


def original():
    return {
        "source_sha_verified": True,
        "independent_equation3_reconciliation_passed": True,
        "variant": "Original_US_1962",
        "months_reconciled": 36,
        "historical_research_statistics": stats(),
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
        "financial_operations": 0,
    }


def rest():
    return {
        "source_sha_verified": True,
        "original_publisher_ods_sha256": sha256(FAKE).hexdigest(),
        "variants_verified": 9,
        "monthly_observations_verified": 324,
        "report": [
            {
                "variant": name,
                "months": 36,
                "independent_cashflow_reconciliation": "PASS",
                "historical_research_statistics": stats(),
            } for name in SHEETS
        ],
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
        "financial_operations": 0,
    }


class SwinkelsSourceBoundTests(unittest.TestCase):
    def receipt(self, *, us=None, other=None):
        with patch.object(s, "SOURCE_SHA", sha256(FAKE).hexdigest()), \
             patch.object(s, "SOURCE_BYTES", len(FAKE)), \
             patch.object(s, "extract_original_us", return_value={}), \
             patch.object(s, "reconcile", return_value=original() if us is None else us), \
             patch.object(s, "reconcile_all_nine", return_value=rest() if other is None else other):
            return s.create_receipt(FAKE)

    def test_source_bytes_always_sha_pinned(self):
        with self.assertRaisesRegex(SourceUnavailable, "source bytes/hash"):
            s.create_receipt(FAKE)
        with self.assertRaisesRegex(SourceUnavailable, "source bytes/hash"):
            s.create_receipt("not bytes")

    def test_consumer_counts_real_series_and_preserves_hold_cash(self):
        result = self.receipt()
        self.assertEqual(result["source_variants"], 10)
        self.assertEqual(result["monthly_observations"], 360)
        self.assertEqual(len(result["source_statistics"]), 10)
        self.assertEqual(result["qualified_model_series"], [])
        self.assertFalse(result["historical_point_in_time_certified"])
        self.assertFalse(result["dataset_2023_erasmus_v6_byte_equivalence_verified"])
        self.assertEqual(result["financial_operations"], 0)
        self.assertTrue(all(x["statistics"]["observations"] == 36
                            for x in result["source_statistics"]))

    def test_missing_months_refused(self):
        x = rest()
        x["monthly_observations_verified"] = 323
        with self.assertRaisesRegex(SourceUnavailable, "proof incomplete"):
            self.receipt(other=x)

    def test_missing_variant_refused(self):
        x = rest()
        x["report"] = x["report"][:-1]
        with self.assertRaisesRegex(SourceUnavailable, "variant coverage"):
            self.receipt(other=x)

    def test_duplicate_variant_refused(self):
        x = rest()
        x["report"][-1]["variant"] = x["report"][0]["variant"]
        with self.assertRaisesRegex(SourceUnavailable, "variant coverage"):
            self.receipt(other=x)

    def test_math_failure_refused(self):
        x = rest()
        x["report"][0]["independent_cashflow_reconciliation"] = "FAIL"
        with self.assertRaisesRegex(SourceUnavailable, "mathematical"):
            self.receipt(other=x)

    def test_wrong_us_model_refused(self):
        x = original()
        x["independent_equation3_reconciliation_passed"] = False
        with self.assertRaisesRegex(SourceUnavailable, "proof incomplete"):
            self.receipt(us=x)

    def test_unverified_source_stats_rejected(self):
        x = rest()
        x["report"][0]["historical_research_statistics"]["historical_pit_certified"] = True
        with self.assertRaisesRegex(SourceUnavailable, "statistics contract"):
            self.receipt(other=x)

    def test_no_financial_operations_allowed(self):
        x = original()
        x["financial_operations"] = 1
        with self.assertRaisesRegex(SourceUnavailable, "proof incomplete"):
            self.receipt(us=x)


if __name__ == "__main__":
    unittest.main()
