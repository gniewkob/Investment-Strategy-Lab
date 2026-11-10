"""Synthetic-only dependency geometry tests. No financial observations."""
import unittest

from scripts.swinkels_multicountry_formula_dependencies_v01 import (
    SourceUnavailable, classify_formula, _column_number
)


class TestSwinkelsMultiCountryFormulaDeps(unittest.TestCase):
    def test_column_number(self):
        self.assertEqual(_column_number("A"), 1)
        self.assertEqual(_column_number("Z"), 26)
        self.assertEqual(_column_number("AA"), 27)

    def test_relative_geometry(self):
        result = classify_formula("of:=([.B20]+[.C19])/[.D20]", 20)
        self.assertEqual(result["reference_geometry"], ((2, 0), (3, -1), (4, 0)))

    def test_row_translation_stable(self):
        before = classify_formula("of:=([.B20]+[.C19])/[.D20]", 20)
        after = classify_formula("of:=([.B21]+[.C20])/[.D21]", 21)
        self.assertEqual(before["reference_geometry"], after["reference_geometry"])
        self.assertEqual(before["shape"], after["shape"])

    def test_operator_drift_detected(self):
        before = classify_formula("of:=([.B20]+[.C19])/[.D20]", 20)
        after = classify_formula("of:=([.B20]-[.C19])/[.D20]", 20)
        self.assertNotEqual(before["operator_counts"], after["operator_counts"])
        self.assertNotEqual(before["shape"], after["shape"])

    def test_nonlocal_sheet_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "unsupported"):
            classify_formula("of:=[Other.C20]+[.B20]", 20)

    def test_out_of_window_dependency_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "cross-period"):
            classify_formula("of:=[.B900]+[.B20]", 20)

    def test_no_references_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "unsupported or missing"):
            classify_formula("of:=100+200", 20)

    def test_no_formula_exposure(self):
        formula = "of:=([.B20]+[.C19])/[.D20]"
        output = classify_formula(formula, 20)
        self.assertEqual(len(output["shape"]), 64)
        self.assertNotIn(formula, str(output))
        self.assertNotIn("B20", str(output))


if __name__ == "__main__":
    unittest.main()
