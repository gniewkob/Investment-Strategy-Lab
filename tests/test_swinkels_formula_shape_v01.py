"""Synthetic unit tests for anonymized source formula structure (no market data)."""
import unittest

from scripts.swinkels_formula_topology_probe_v01 import (
    _formula_shape_digest, SourceUnavailable,
)


class FormulaShapeTests(unittest.TestCase):
    def test_same_operator_structure_different_cell_rows(self):
        a = _formula_shape_digest("of:=([.B10]+[.C10])*[.D10]")
        b = _formula_shape_digest("of:=([.B11]+[.C11])*[.D11]")
        self.assertEqual(a, b)

    def test_operator_drift_detected(self):
        a = _formula_shape_digest("of:=([.B10]+[.C10])*[.D10]")
        b = _formula_shape_digest("of:=([.B10]-[.C10])*[.D10]")
        self.assertNotEqual(a, b)

    def test_constant_change_anonymized(self):
        a = _formula_shape_digest("of:=([.A10]+0.5)*[.B10]")
        b = _formula_shape_digest("of:=([.A11]+0.7)*[.B11]")
        self.assertEqual(a, b)

    def test_missing_reference_rejected(self):
        with self.assertRaises(SourceUnavailable):
            _formula_shape_digest("of:=1+2")

    def test_invalid_formula_prefix_rejected(self):
        with self.assertRaises(SourceUnavailable):
            _formula_shape_digest("=SUM([.A10])")

    def test_formula_not_returned_directly(self):
        expression = "of:=([.B10]+[.C10])*[.D10]"
        digest = _formula_shape_digest(expression)
        self.assertEqual(len(digest), 64)
        self.assertNotIn("B10", digest)


if __name__ == "__main__":
    unittest.main()
