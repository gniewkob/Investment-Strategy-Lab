"""Synthetic-only v0.23 forward admission tests, no real future NAV."""
from datetime import datetime, timezone
from unittest.mock import patch
import unittest

from scripts.nav_forward_freeze_v22 import freeze
from scripts import nav_forward_admission_v23 as v23
from tests.test_conditional_m1_nav_diagnostic_v20 import sample_receipt

FREEZE_AT=datetime(2026,11,7,20,tzinfo=timezone.utc)
BEFORE=datetime(2026,11,8,20,tzinfo=timezone.utc)
LATER=datetime(2026,12,5,20,tzinfo=timezone.utc)


def fixture():
    frozen=freeze(sample_receipt(),clock=lambda:FREEZE_AT)
    candidate={
        "month":"2026-11",
        "observed_for":"2026-11-30",
        "nav_usd":"175.00",
        "usdpln_nbp":"4.0",
        "nav_pln_reference":"700.000",
        "original_export_sha256":"a"*64,
        "original_export_retrieved_at_utc":"2026-12-02T12:00:00+00:00",
        "nbp_original_response_sha256":"b"*64,
        "nbp_retrieved_at_utc":"2026-12-01T12:00:00+00:00",
        "nbp_source_url":"https://api.nbp.pl/api/exchangerates/tables/a/2026-11-30/2026-11-30/?format=json",
    }
    return frozen,candidate


class NavForwardAdmissionV23Tests(unittest.TestCase):
    def anchored(self,frozen,candidate=None,now=BEFORE):
        with patch.object(v23,"ANCHORED_FREEZE_SHA",frozen["freeze_receipt_sha256"]):
            return v23.admission(frozen,candidate,clock=lambda:now)

    def test_anchored_pending_when_no_future_record(self):
        frozen,_=fixture()
        out=self.anchored(frozen)
        self.assertEqual(out["status"],"PENDING_FIRST_POST_FREEZE_ORIGINAL_MONTH")
        self.assertEqual(out["prospective_eligible_reference_months"],0)
        self.assertTrue(out["anchor_sha_matched"])
        self.assertFalse(out["strict_m1_model_qualified"])
        self.assertEqual(out["financial_operations"],0)

    def test_wrong_anchored_freeze_is_rejected(self):
        frozen,_=fixture()
        with self.assertRaisesRegex(ValueError,"prepublished GitHub"):
            v23.admission(frozen,clock=lambda:BEFORE)

    def test_future_month_cannot_be_admitted_in_november(self):
        frozen,candidate=fixture()
        with self.assertRaisesRegex(ValueError,"not yet complete"):
            self.anchored(frozen,candidate,BEFORE)

    def test_late_inspection_must_not_admit_partial_november_export(self):
        frozen,candidate=fixture()
        candidate["observed_for"]="2026-11-20"
        candidate["nbp_source_url"]=candidate["nbp_source_url"].replace(
            "2026-11-30/2026-11-30", "2026-11-20/2026-11-20")
        candidate["original_export_retrieved_at_utc"]="2026-11-21T12:00:00+00:00"
        with self.assertRaisesRegex(ValueError,"completed month"):
            self.anchored(frozen,candidate,LATER)

    def test_later_candidate_is_still_unqualified_and_nonexecutible(self):
        frozen,candidate=fixture()
        result=self.anchored(frozen,candidate,LATER)
        self.assertEqual(result["status"],
                         "CANDIDATE_FORWARD_REFERENCE_REQUIRES_INDEPENDENT_SOURCE_REVIEW")
        self.assertEqual(result["prospective_eligible_reference_months"],0)
        self.assertFalse(result["candidate_provenance_independently_verified"])
        self.assertFalse(result["out_of_sample_investment_performance_proven"])
        self.assertEqual(result["orders_sent"],0)
        self.assertEqual(result,self.anchored(frozen,candidate,LATER))

    def test_prior_month_and_old_export_rejected(self):
        frozen,candidate=fixture()
        candidate["month"]="2026-10"
        with self.assertRaisesRegex(ValueError,"first planned"):
            self.anchored(frozen,candidate,LATER)
        _,candidate=fixture()
        candidate["original_export_sha256"]=frozen["original_nav_file_sha256"]
        with self.assertRaisesRegex(ValueError,"old original export"):
            self.anchored(frozen,candidate,LATER)

    def test_missing_or_wrong_exact_date_fx_rejected(self):
        frozen,candidate=fixture()
        candidate["nbp_source_url"]=candidate["nbp_source_url"].replace(
            "2026-11-30/2026-11-30","2026-11-29/2026-11-29")
        with self.assertRaisesRegex(ValueError,"exact-day"):
            self.anchored(frozen,candidate,LATER)
        _,candidate=fixture()
        candidate["nav_pln_reference"]="999"
        with self.assertRaisesRegex(ValueError,"multiplication"):
            self.anchored(frozen,candidate,LATER)

    def test_retrieval_before_freeze_or_after_now_fails(self):
        frozen,candidate=fixture()
        candidate["original_export_retrieved_at_utc"]="2026-11-06T12:00:00+00:00"
        with self.assertRaisesRegex(ValueError,"must follow"):
            self.anchored(frozen,candidate,LATER)
        _,candidate=fixture()
        candidate["nbp_retrieved_at_utc"]="2026-12-06T12:00:00+00:00"
        with self.assertRaisesRegex(ValueError,"must follow"):
            self.anchored(frozen,candidate,LATER)

    def test_invalid_sha_and_unexpected_extra_field_rejected(self):
        frozen,candidate=fixture()
        candidate["original_export_sha256"]="not-a-real-hash"
        with self.assertRaisesRegex(ValueError,"SHA-256"):
            self.anchored(frozen,candidate,LATER)
        _,candidate=fixture()
        candidate["pretend_qualified"]=True
        with self.assertRaisesRegex(ValueError,"exact future"):
            self.anchored(frozen,candidate,LATER)

    def test_freeze_integrity_rejected_before_any_candidate(self):
        frozen,_=fixture()
        frozen["declared_policy"]["monthly_contribution_pln"]="500"
        with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
            self.anchored(frozen,None,BEFORE)


if __name__=="__main__":
    unittest.main()
