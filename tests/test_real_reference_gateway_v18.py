"""v0.18 official reference gateway: real semantics stay non-executable."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

from scripts.real_reference_gateway_v18 import evaluate_reference
from scripts.shadow_decision_engine_v05 import ShadowInputError
from scripts.reference_archive_calendar_v04 import _digest
from tests.test_shadow_decision_engine_v05 import make_months


def fixture():
    # Synthetic calendar structure only. CI real-source workflow downloads
    # actual 60-month NBP/BondSpot archive independently.
    timeline = [{"month": r["month"], "same_calendar_date": True}
                for r in make_months(60)]
    doc = {
        "status": "SAME_CALENDAR_DATE_REFERENCE_NOT_PIT_OR_EXECUTABLE",
        "months": 60,
        "first_month": "2021-11",
        "last_month": "2026-10",
        "timeline": timeline,
        "financial_operations": 0,
        "paper_events_created": 0,
    }
    doc["evidence_sha256"] = _digest(doc)
    return doc


class RealReferenceGatewayV18Tests(unittest.TestCase):
    def test_reference_families_never_become_tr_models(self):
        report = evaluate_reference(fixture(), as_of_utc="2026-11-07T15:00:00+00:00")
        self.assertEqual(report["status"], "REFERENCE_DATA_OBSERVED_MODELS_BLOCKED")
        self.assertEqual(report["reference_months"], 60)
        self.assertEqual(report["qualified_total_return_model_series"], [])
        self.assertEqual(len(report["missing_qualified_model_series"]), 3)
        self.assertEqual(report["model_states"], {
            "M1_GLOBAL_EQ": "HOLD_CASH",
            "M2_DIVERSIFIED": "HOLD_CASH",
            "M3_TACTICAL": "HOLD_CASH",
        })
        self.assertEqual(report["candidate_models"], [])
        self.assertEqual(report["real_reference_families"]["NBP_GOLD_PLN_G"],
                         "PRICE_ONLY_NOT_TOTAL_RETURN")
        self.assertEqual(report["real_reference_families"]["NBP_USDPLN"],
                         "FX_RATE_NOT_TOTAL_RETURN")
        self.assertEqual(report["real_reference_families"]["BONDSPOT_TBSP_INDEX"],
                         "NON_TRADABLE_BOND_BENCHMARK")
        self.assertFalse(report["historical_pit_certified"])
        self.assertEqual(report["financial_operations"], 0)

    def test_digest_replays_deterministically_without_input_changes(self):
        data = fixture()
        before = deepcopy(data)
        x = evaluate_reference(data, as_of_utc="2026-11-07T15:00:00Z")
        y = evaluate_reference(data, as_of_utc="2026-11-07T15:00:00Z")
        self.assertEqual(x, y)
        self.assertEqual(data, before)

    def test_modified_archive_rejected(self):
        data = fixture()
        data["timeline"][0]["month"] = "2000-01"
        with self.assertRaisesRegex(ShadowInputError, "fingerprint mismatch"):
            evaluate_reference(data, as_of_utc="2026-11-07T15:00:00Z")

    def test_missing_evaluation_time_rejected(self):
        with self.assertRaisesRegex(ShadowInputError, "explicit UTC"):
            evaluate_reference(fixture())

    def test_premature_or_same_month_asof_rejected(self):
        for instant in ("2026-10-31T23:00:00Z", "2026-09-01T00:00:00Z"):
            with self.subTest(instant=instant), self.assertRaisesRegex(
                    ShadowInputError, "follow final completed"):
                evaluate_reference(fixture(), as_of_utc=instant)

    def test_wrong_archive_identity_rejected(self):
        data = fixture()
        data["status"] = "REAL_TRADING"
        with self.assertRaisesRegex(ShadowInputError, "not accepted"):
            evaluate_reference(data, as_of_utc="2026-11-07T15:00:00Z")

    def test_malformed_evaluation_date_rejected(self):
        with self.assertRaises(ShadowInputError):
            evaluate_reference(fixture(), as_of_utc="not-datetime")


if __name__ == "__main__":
    unittest.main()
