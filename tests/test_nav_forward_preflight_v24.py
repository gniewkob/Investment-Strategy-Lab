"""v0.24 tests use invented synthetic XLSX and NBP API replies only."""
from datetime import datetime, timezone
from unittest.mock import patch
import json
import unittest

from scripts.nav_forward_freeze_v22 import freeze
from scripts import nav_forward_admission_v23 as v23
from scripts.nav_forward_preflight_v24 import preflight
from tests.test_conditional_m1_nav_diagnostic_v20 import sample_receipt
from tests.test_vanguard_xlsx_offline_intake_v04 import fake_xlsx

FREEZE_AT=datetime(2026,11,7,20,tzinfo=timezone.utc)
NOV=datetime(2026,11,8,20,tzinfo=timezone.utc)
DEC=datetime(2026,12,5,20,tzinfo=timezone.utc)
NOV_FX=json.dumps([{
    "table":"A","effectiveDate":"2026-11-30",
    "rates":[{"code":"USD","mid":4.0}]
}]).encode()


def sources():
    baseline=sample_receipt()
    frozen=freeze(baseline,clock=lambda:FREEZE_AT)
    return frozen,baseline


def evaluate(frozen, baseline, **kw):
    with patch.object(v23,"ANCHORED_FREEZE_SHA",frozen["freeze_receipt_sha256"]):
        return preflight(frozen,baseline,**kw)


class NAVForwardPreflightV24Tests(unittest.TestCase):
    def test_existing_freeze_reports_pending_zero_future_months(self):
        frozen,baseline=sources()
        output=evaluate(frozen,baseline,clock=lambda:NOV)
        self.assertEqual(output["status"],
                         "PENDING_NEXT_COMPLETE_MONTH_OR_NEW_ORIGINAL_EXPORT")
        self.assertEqual(output["prospective_eligible_months"],0)
        self.assertEqual(output["financial_operations"],0)
        self.assertIsNone(output["future_candidate_observed_for"])
        self.assertEqual(output,evaluate(frozen,baseline,clock=lambda:NOV))

    def test_partial_month_rejects_early_export(self):
        frozen,baseline=sources()
        with self.assertRaisesRegex(ValueError,"partial November"):
            evaluate(frozen,baseline,raw_export=fake_xlsx(61),
                     raw_nbp=NOV_FX,clock=lambda:NOV)

    def test_source_pair_cannot_be_half_present(self):
        frozen,baseline=sources()
        with self.assertRaisesRegex(ValueError,"both required"):
            evaluate(frozen,baseline,raw_export=fake_xlsx(61),clock=lambda:DEC)

    def test_new_synthetic_export_revisions_fail_close(self):
        frozen,baseline=sources()
        out=evaluate(frozen,baseline,raw_export=fake_xlsx(61),
                     raw_nbp=NOV_FX,clock=lambda:DEC,
                     export_retrieved_at_utc="2026-12-02T12:00:00+00:00",
                     nbp_retrieved_at_utc="2026-12-01T12:00:00+00:00")
        self.assertEqual(out["status"],
                         "BLOCKED_HISTORICAL_SOURCE_REVISIONS_REQUIRE_REVIEW")
        self.assertGreater(out["historical_revisions_count"],0)
        self.assertEqual(out["prospective_eligible_months"],0)

    def test_wrong_baseline_source_sha_rejected(self):
        frozen,baseline=sources()
        baseline["monthly"][0]["nav_usd"]="999"
        with self.assertRaisesRegex(ValueError,"SHA-256"):
            evaluate(frozen,baseline,clock=lambda:NOV)

    def test_unanchored_freeze_rejected(self):
        frozen,baseline=sources()
        with self.assertRaisesRegex(ValueError,"prepublished GitHub"):
            preflight(frozen,baseline,clock=lambda:NOV)


if __name__=="__main__":
    unittest.main()
