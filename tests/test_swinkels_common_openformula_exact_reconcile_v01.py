"""Synthetic-only safe OpenFormula replay tests. No financial source observations."""
import unittest

from scripts.swinkels_common_openformula_exact_reconcile_v01 import (
    SourceUnavailable, normalize_source_formula, safe_formula_math,
)


class CommonSourceFormulaTests(unittest.TestCase):
    def test_local_yield_previous_and_current_mapping(self):
        form = "of:=([.B20]+[.B19]+[.B20]+[.B19]+[.B20])/100"
        normalized = normalize_source_formula(form, 20)
        self.assertEqual(normalized, "(Y_CURR+Y_PREV+Y_CURR+Y_PREV+Y_CURR)/100")

    def test_original_formula_operators(self):
        f = "of:=([.B20]/200+1)^2-([.B19]/1200)+[.B20]/[.B19]+[.B20]"
        normalized = normalize_source_formula(f, 20)
        self.assertIn("**2", normalized)
        self.assertEqual(len(normalized), len(normalized))

    def test_exact_fixed_arithmetic_with_explicit_percent_points(self):
        expression = "(Y_PREV/1200)+((Y_PREV-Y_CURR)/100)"
        self.assertAlmostEqual(safe_formula_math(expression, 3.0, 4.0), -0.0075, places=12)

    def test_exponent_math(self):
        self.assertAlmostEqual(
            safe_formula_math("(1+Y_CURR/200)**2-1", 3.0, 4.0),
            1.02**2 - 1,
            places=12,
        )

    def test_evil_python_call_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "unsupported"):
            safe_formula_math("__import__('os')", 3.0, 4.0)

    def test_evil_python_attribute_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "unsupported"):
            safe_formula_math("Y_PREV.__class__", 3.0, 4.0)

    def test_nonlocal_worksheet_reference_rejected(self):
        formula = "of:=[Other.B20]+[.B19]+[.B20]+[.B19]+[.B20]"
        with self.assertRaises(SourceUnavailable):
            normalize_source_formula(formula, 20)

    def test_source_nonadjacent_month_reference_rejected(self):
        formula = "of:=[.B20]+[.B18]+[.B20]+[.B19]+[.B20]"
        with self.assertRaisesRegex(SourceUnavailable, "nonadjacent"):
            normalize_source_formula(formula, 20)

    def test_formula_missing_references_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "five"):
            normalize_source_formula("of:=(1+1)", 20)

    def test_extreme_literal_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "literal"):
            safe_formula_math("999999999999+Y_PREV", 3.0, 4.0)

    def test_division_by_zero_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "evaluation failed"):
            safe_formula_math("Y_CURR/(Y_PREV-Y_PREV)", 3.0, 4.0)

    def test_unknown_yield_symbol_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "unsupported"):
            safe_formula_math("Y_EVIL+100", 3.0, 4.0)


if __name__ == "__main__":
    unittest.main()
