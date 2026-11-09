"""Synthetic v0.22 prospective freeze tests, no original NAV data or trades."""
from copy import deepcopy
from datetime import datetime, timezone
import unittest

from scripts.nav_forward_freeze_v22 import freeze, verify_pending
from scripts.reference_archive_calendar_v04 import _digest
from tests.test_conditional_m1_nav_diagnostic_v20 import sample_receipt


NOW = datetime(2026, 11, 7, 20, tzinfo=timezone.utc)


class NAVForwardFreezeTests(unittest.TestCase):
    def test_freeze_pending_and_source_identity(self):
        source = sample_receipt()
        original = deepcopy(source)
        result = freeze(source, clock=lambda: NOW)
        self.assertEqual(source, original)
        self.assertEqual(result["status"], "FROZEN_PENDING_FIRST_FUTURE_MONTH")
        self.assertEqual(result["forward_qualified_months"], 0)
        self.assertEqual(result["first_forward_month"], "2026-11")
        self.assertEqual(result["source_evidence_sha256"], source["evidence_sha256"])
        self.assertEqual(verify_pending(result, clock=lambda: NOW)["status"],
                         "PENDING_NO_PROSPECTIVE_DATA")
        self.assertEqual(result, freeze(source, clock=lambda: NOW))
        self.assertFalse(result["strict_m1_model_qualified"])
        self.assertEqual(result["financial_operations"], 0)

    def test_no_retroactive_or_late_freeze(self):
        for day in (datetime(2026, 10, 31, tzinfo=timezone.utc),
                    datetime(2026, 12, 1, tzinfo=timezone.utc)):
            with self.subTest(day=day), self.assertRaisesRegex(ValueError, "during November"):
                freeze(sample_receipt(), clock=lambda: day)

    def test_tampered_source_rejected(self):
        source = sample_receipt()
        source["monthly"][3]["nav_usd"] = "98765"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            freeze(source, clock=lambda: NOW)

    def test_freeze_rejects_fake_forward_results(self):
        doc = freeze(sample_receipt(), clock=lambda: NOW)
        doc["forward_qualified_months"] = 1
        doc["forward_observations"] = [{"fake": True}]
        doc["freeze_receipt_sha256"] = _digest({
            k: v for k, v in doc.items() if k != "freeze_receipt_sha256"})
        with self.assertRaisesRegex(ValueError, "cannot claim forward"):
            verify_pending(doc, clock=lambda: NOW)

    def test_integrity_and_utc_checks(self):
        doc = freeze(sample_receipt(), clock=lambda: NOW)
        doc["declared_policy"]["monthly_contribution_pln"] = "500"
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            verify_pending(doc, clock=lambda: NOW)
        doc = freeze(sample_receipt(), clock=lambda: NOW)
        with self.assertRaisesRegex(ValueError, "future"):
            verify_pending(doc, clock=lambda: datetime(2026, 11, 6, tzinfo=timezone.utc))

    def test_strict_gate_rejected_even_resealed(self):
        doc = freeze(sample_receipt(), clock=lambda: NOW)
        doc["strict_m1_model_qualified"] = True
        doc["freeze_receipt_sha256"] = _digest({
            k: v for k, v in doc.items() if k != "freeze_receipt_sha256"})
        with self.assertRaisesRegex(ValueError, "cannot claim forward"):
            verify_pending(doc, clock=lambda: NOW)


if __name__ == "__main__":
    unittest.main()
