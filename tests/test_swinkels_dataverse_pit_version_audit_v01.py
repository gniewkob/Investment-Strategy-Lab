"""Synthetic-only Swinkels dataset version chronology and PIT fail-closed tests."""
import unittest

from scripts.swinkels_dataverse_pit_version_audit_v01 import (
    SourceUnavailable, _release_date, audit_release_timeline,
)


def version(number, release_time, ids, state="RELEASED", pid="doi:10.34894/YWT2IX"):
    result = {
        "versionNumber": number,
        "versionMinorNumber": 0,
        "versionState": state,
        "releaseTime": release_time,
        "datasetPersistentId": pid,
    }
    if ids is not None:
        result["files"] = [{"dataFile": {"id": value}} for value in ids]
    return result


class PublisherVersionPITTests(unittest.TestCase):
    def test_2023_file_version_cannot_qualify_2020_2022(self):
        result = audit_release_timeline([
            version(6, "2023-03-05T10:00:00Z", [512630, 512631]),
        ], True)
        self.assertEqual(result["earliest_exposed_release_of_file_id"], "2023-03-05")
        self.assertEqual(
            result["source_release_chronology"],
            "LISTED_FILE_ID_FIRST_RELEASE_AFTER_2022_WINDOW",
        )
        self.assertFalse(result["point_in_time_decision_eligible"])
        self.assertEqual(result["qualified_model_series"], [])
        self.assertEqual(result["model_state"], "HOLD_CASH")

    def test_pre2023_version_still_not_proof_of_underlying_vintages(self):
        result = audit_release_timeline([
            version(1, "2021-06-01T11:00:00+00:00", [512630]),
        ], True)
        self.assertEqual(
            result["source_release_chronology"],
            "PRE_2023_VERSION_EXISTS_NOT_PIT_CERTIFICATION",
        )
        self.assertFalse(result["underlying_yield_vintage_linked"])
        self.assertFalse(result["point_in_time_decision_eligible"])

    def test_unexposed_version_file_lists_are_not_proof(self):
        result = audit_release_timeline([
            version(2, "2022-07-01T12:00:00Z", None),
        ], True)
        self.assertEqual(result["earliest_exposed_release_of_file_id"], None)
        self.assertEqual(result["source_release_chronology"], "EXACT_FILE_RELEASE_DATE_UNRESOLVED")

    def test_draft_is_not_publication(self):
        result = audit_release_timeline([
            version(2, "2021-06-01T00:00:00Z", [512630], state="DRAFT"),
            version(3, "2023-02-01T00:00:00Z", [512630]),
        ], True)
        self.assertEqual(result["earliest_exposed_release_of_file_id"], "2023-02-01")

    def test_publisher_pid_mismatch_blocks(self):
        with self.assertRaisesRegex(SourceUnavailable, "identifier mismatch"):
            audit_release_timeline([version(1, "2023-01-01T00:00:00Z", [512630], pid="doi:fake")], True)

    def test_hash_not_verified_blocks(self):
        with self.assertRaisesRegex(SourceUnavailable, "digest"):
            audit_release_timeline([version(1, "2023-01-01T00:00:00Z", [512630])], False)

    def test_zero_versions_blocks(self):
        with self.assertRaisesRegex(SourceUnavailable, "inventory"):
            audit_release_timeline([], True)

    def test_duplicate_version_blocks(self):
        with self.assertRaisesRegex(SourceUnavailable, "duplicate"):
            audit_release_timeline([
                version(1, "2023-01-01T00:00:00Z", [512630]),
                version(1, "2023-03-01T00:00:00Z", [512630]),
            ], True)

    def test_naive_timestamp_not_public_release_evidence(self):
        self.assertIsNone(_release_date("2023-05-01T00:00:00"))

    def test_utc_timestamp_date_conversion(self):
        self.assertEqual(_release_date("2023-01-01T01:00:00+02:00"), "2022-12-31")

    def test_file_id_missing_is_distinct_from_no_list(self):
        result = audit_release_timeline([version(2, "2023-02-01T00:00:00Z", [9999])], True)
        self.assertEqual(result["version_inventory"][0]["file_id_membership"], "NOT_MEMBER")
        self.assertIsNone(result["earliest_exposed_release_of_file_id"])


if __name__ == "__main__":
    unittest.main()
