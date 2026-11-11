"""Active v0.26 original-source month gate; frozen v0.23 remains byte-identical."""
from datetime import datetime, timezone
from unittest.mock import patch
import unittest

from scripts import nav_forward_admission_v23 as v23
from scripts.nav_forward_admission_v26 import admission
from tests.test_nav_forward_admission_v23 import fixture

DEC=datetime(2026,12,5,20,tzinfo=timezone.utc)


class NavAdmissionV26Tests(unittest.TestCase):
    def accepted(self,frozen,candidate=None):
        with patch.object(v23,"ANCHORED_FREEZE_SHA",frozen["freeze_receipt_sha256"]):
            return admission(frozen,candidate,clock=lambda:DEC)

    def test_direct_call_rejects_partial_month_provider_export_in_later_december(self):
        frozen,candidate=fixture()
        candidate["observed_for"]="2026-11-21"
        candidate["original_export_retrieved_at_utc"]="2026-11-22T15:00:00+00:00"
        candidate["nbp_source_url"]=(
            "https://api.nbp.pl/api/exchangerates/tables/a/"
            "2026-11-21/2026-11-21/?format=json")
        with self.assertRaisesRegex(ValueError,"completed observed month"):
            self.accepted(frozen,candidate)

    def test_completed_month_source_receipt_is_still_unqualified(self):
        frozen,candidate=fixture()
        result=self.accepted(frozen,candidate)
        self.assertEqual(result["status"],"CANDIDATE_FORWARD_REFERENCE_REQUIRES_INDEPENDENT_SOURCE_REVIEW")
        self.assertFalse(result["strict_m1_model_qualified"])
        self.assertEqual(result["financial_operations"],0)

    def test_no_source_keeps_original_pending_gate(self):
        frozen,_=fixture()
        result=self.accepted(frozen)
        self.assertEqual(result["status"],"PENDING_FIRST_POST_FREEZE_ORIGINAL_MONTH")


if __name__=="__main__":
    unittest.main()
