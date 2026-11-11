"""Synthetic-only contract tests; nothing here authorizes model admissions."""
import copy
import unittest
from datetime import date, timedelta

from src.isl_v2.total_return_evidence_preflight import (
    EvidenceContractBlocked, inspect_total_return_evidence,
    EXPECTED_INSTRUMENTS,
)

CUTOFF = "2026-10-17T07:00:00Z"


def fixture():
    rows = []
    for instrument in EXPECTED_INSTRUMENTS:
        for idx, month in enumerate(("2026-06", "2026-07", "2026-08", "2026-09")):
            last_day = date(int(month[:4]), int(month[5:7]), 28)
            rows.append({
                "instrument_code": instrument,
                "source_code": "publisher_index",
                "official_series_id": "official_" + instrument,
                "currency": "PLN",
                "value_concept": "TOTAL_RETURN_INDEX",
                "return_basis": "GROSS_TOTAL_RETURN",
                "interval_code": "1mo",
                "month": month,
                "observed_for": last_day.isoformat() + "T00:00:00Z",
                "price_value": str(100 + idx),
                "source_url": "https://example.org/indices/monthly",
                "source_sha256": "a" * 64,
                "source_version": "v1.2.3",
                "first_public_at": (last_day + timedelta(days=1)).isoformat() + "T10:00:00Z",
                "retrieved_at": (last_day + timedelta(days=2)).isoformat() + "T10:00:00Z",
                "publication_precision": "EXACT",
                "license_url": "https://example.org/license",
                "transformation_version": "transform_v1",
            })
    return rows


class TotalReturnEvidencePreflightTests(unittest.TestCase):
    def test_complete_shape_is_not_model_approval(self):
        receipt = inspect_total_return_evidence(fixture(), decision_asof=CUTOFF)
        self.assertEqual(receipt["observations_checked"], 12)
        self.assertEqual(receipt["structural_evidence_consistency"], "PASS")
        self.assertEqual(receipt["independent_source_authentication"], "NOT_PERFORMED")
        self.assertFalse(receipt["model_admission_granted"])
        self.assertFalse(receipt["historical_pit_certified"])
        self.assertEqual(receipt["qualified_model_series"], [])
        self.assertEqual(receipt["research_model_state"], "HOLD_CASH")
        self.assertEqual(receipt["financial_operations"], 0)

    def assert_blocks(self, code, rows=None, *, cutoff=CUTOFF):
        with self.assertRaisesRegex(EvidenceContractBlocked, code):
            inspect_total_return_evidence(fixture() if rows is None else rows, decision_asof=cutoff)

    def test_data_provider_assertion_cannot_auto_authorize(self):
        rows = fixture()
        for row in rows:
            row.update({"is_approved": True, "PIT_VERIFIED": True, "provider_trusted": True})
        self.assertFalse(inspect_total_return_evidence(rows, decision_asof=CUTOFF)["model_admission_granted"])

    def test_missing_issuer_series_id(self):
        rows = fixture()
        rows[0].pop("official_series_id")
        self.assert_blocks("REQUIRED_EVIDENCE_MISSING", rows)

    def test_wrong_instrument(self):
        rows = fixture()
        rows[0]["instrument_code"] = "FAKE_TR_PLN"
        self.assert_blocks("UNKNOWN_INSTRUMENT", rows)

    def test_non_pln_currency(self):
        rows = fixture()
        rows[0]["currency"] = "USD"
        self.assert_blocks("NON_PLN_PRICE_BASIS", rows)

    def test_price_only_laundering(self):
        rows = fixture()
        rows[0]["value_concept"] = "MONTHLY_AVERAGE"
        self.assert_blocks("NOT_TOTAL_RETURN_INDEX", rows)

    def test_missing_price_return_basis(self):
        rows = fixture()
        rows[0]["return_basis"] = "PRICE_ONLY"
        self.assert_blocks("RETURN_BASIS_UNSPECIFIED", rows)

    def test_non_monthly(self):
        rows = fixture()
        rows[0]["interval_code"] = "1d"
        self.assert_blocks("NOT_MONTHLY", rows)

    def test_invalid_index_level(self):
        rows = fixture()
        rows[0]["price_value"] = "NaN"
        self.assert_blocks("NONPOSITIVE_OR_INVALID_INDEX_LEVEL", rows)

    def test_missing_sha(self):
        rows = fixture()
        rows[0]["source_sha256"] = "not-a-hash"
        self.assert_blocks("MISSING_VERIFIABLE_SHA256", rows)

    def test_non_https_license(self):
        rows = fixture()
        rows[0]["license_url"] = "http://example.org/license"
        self.assert_blocks("INVALID_SOURCE_OR_LICENSE_URL", rows)

    def test_noncanonical_source_url_query(self):
        rows = fixture()
        rows[0]["source_url"] = "https://example.org/?apikey=123"
        self.assert_blocks("INVALID_SOURCE_OR_LICENSE_URL", rows)

    def test_observation_month_mismatch(self):
        rows = fixture()
        rows[0]["month"] = "2026-05"
        self.assert_blocks("OBSERVATION_MONTH_MISMATCH", rows)

    def test_publication_after_decision(self):
        rows = fixture()
        rows[0]["first_public_at"] = "2026-11-10T00:00:00Z"
        rows[0]["retrieved_at"] = "2026-11-11T00:00:00Z"
        self.assert_blocks("PUBLICATION_AFTER_DECISION", rows)

    def test_retrospective_retrieval_is_not_pit(self):
        rows = fixture()
        rows[0]["retrieved_at"] = "2026-11-10T00:00:00Z"
        self.assert_blocks("ARCHIVE_RETRIEVED_AFTER_DECISION", rows)

    def test_day_precision_release_at_decision_same_day_is_blocked(self):
        rows = fixture()
        rows[0]["publication_precision"] = "DAY"
        rows[0]["first_public_at"] = "2026-10-17T00:00:00Z"
        rows[0]["retrieved_at"] = "2026-10-17T06:00:00Z"
        self.assert_blocks("PUBLICATION_AFTER_DECISION", rows)

    def test_duplicate_month(self):
        rows = fixture()
        rows[1] = copy.deepcopy(rows[0])
        self.assert_blocks("DUPLICATE_INSTRUMENT_MONTH", rows)

    def test_nonconsecutive_months(self):
        rows = fixture()
        rows[3]["month"] = "2026-11"
        rows[3]["observed_for"] = "2026-11-28T00:00:00Z"
        rows[3]["first_public_at"] = "2026-11-29T10:00:00Z"
        rows[3]["retrieved_at"] = "2026-11-30T10:00:00Z"
        self.assert_blocks("PUBLICATION_AFTER_DECISION", rows)
        # Move cutoff beyond the synthetic later data to isolate continuity.
        self.assert_blocks("NONCONSECUTIVE_MONTHS", rows, cutoff="2026-12-31T00:00:00Z")

    def test_missing_instrument_month(self):
        rows = fixture()
        del rows[0]
        self.assert_blocks("FOUR_MONTH_COVERAGE_INCOMPLETE", rows)

    def test_inconsistent_series_identifier(self):
        rows = fixture()
        rows[0]["official_series_id"] = "replacement"
        self.assert_blocks("INCONSISTENT_SOURCE_SERIES_ID", rows)

    def test_ambiguous_datetime(self):
        rows = fixture()
        rows[0]["first_public_at"] = "2026-07-01T10:00:00"
        self.assert_blocks("TIMESTAMP_MISSING_OR_AMBIGUOUS", rows)

    def test_empty_observations(self):
        self.assert_blocks("EVIDENCE_SET_INVALID_SIZE", [])

    def test_future_month_after_cutoff(self):
        rows = fixture()
        self.assert_blocks("PUBLICATION_AFTER_DECISION", rows, cutoff="2026-08-01T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
