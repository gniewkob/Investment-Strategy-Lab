"""Synthetic-only bridge tests; no real historical data or network."""
import copy
import unittest

from scripts.paper_equity_reference_bridge import compare_with_equity_marks
from scripts.paper_multi_asset_research_v02 import MultiAssetBlocked, synthetic_manifest


class EquityBridgeTests(unittest.TestCase):
    def setUp(self):
        self.manifest = synthetic_manifest()
        self.manifest["source_class"] = "UNVERIFIED_EXTERNAL"
        self.marks = [{"month": row["month"], "equity_date": row["month"] + "-25",
                       "equity_eur": "100", "fx_date": row["month"] + "-24",
                       "pln_per_eur": "4"} for row in self.manifest["observations"]]

    def test_bridge_produces_non_executable_research_comparison(self):
        before = copy.deepcopy((self.manifest, self.marks))
        report = compare_with_equity_marks(self.manifest, self.marks)
        self.assertEqual(before, (self.manifest, self.marks))
        self.assertEqual(report["months"], 60)
        self.assertEqual(report["nominal_contributions_pln"], "6000.00")
        self.assertEqual(report["source_class"], "UNVERIFIED_EXTERNAL")
        self.assertFalse(report["equity_bridge"]["source_identity_rights_and_completeness_verified"])
        self.assertFalse(report["historical_point_in_time_certified"])
        self.assertFalse(report["executable_prices_certified"])
        self.assertEqual(report["qualified_total_return_series"], [])

    def test_changes_equity_path_and_preserves_other_assets(self):
        first = compare_with_equity_marks(self.manifest, self.marks)
        self.marks[-1]["equity_eur"] = "200"
        second = compare_with_equity_marks(self.manifest, self.marks)
        self.assertGreater(float(second["strategies"][0]["terminal_value_pln"]),
                           float(first["strategies"][0]["terminal_value_pln"]))
        self.assertNotEqual(first["input_sha256"], second["input_sha256"])

    def test_rejects_missing_duplicate_cross_month_and_stale_marks(self):
        for mutate in (lambda x: x.pop(),
                       lambda x: x.__setitem__(1, copy.deepcopy(x[0])),
                       lambda x: x[0].update(fx_date="2021-02-01"),
                       lambda x: x[0].update(fx_date="2021-01-01"),
                       lambda x: x[0].update(equity_date="20210125")):
            marks = copy.deepcopy(self.marks)
            mutate(marks)
            with self.subTest(mutate=mutate), self.assertRaises(MultiAssetBlocked):
                compare_with_equity_marks(self.manifest, marks)

    def test_rejects_invalid_values_and_wrong_source_class(self):
        for value in ("0", "NaN", "-1", 1.0, True):
            marks = copy.deepcopy(self.marks)
            marks[0]["pln_per_eur"] = value
            with self.subTest(value=value), self.assertRaises(MultiAssetBlocked):
                compare_with_equity_marks(self.manifest, marks)
        self.manifest["source_class"] = "SYNTHETIC"
        with self.assertRaisesRegex(MultiAssetBlocked, "UNVERIFIED_SOURCE"):
            compare_with_equity_marks(self.manifest, self.marks)


if __name__ == "__main__":
    unittest.main()
