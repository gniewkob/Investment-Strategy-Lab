"""I7 NBP archived filename vs API metadata checks; synthetic, no market data."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

from scripts.nbp_archive_directory_reconcile_v01 import (
    NBPDirectoryError, _archive_inventory, _read_directory, reconcile_archive,
)
from tests.test_nbp_publication_lag_offline_v01 import sample


DIR = b"a213z261029\nb030z261029\na214z261030\nc214z261030\na215z261102\n"
DATE = "2026-10-30"
LATER = "2026-10-31T00:00:00Z"


def check(snapshot=None, archive=DIR, *, day=DATE, instant=LATER, year=2026):
    return reconcile_archive(
        sample() if snapshot is None else snapshot, archive,
        archive_year=year,
        requested_effective_date=day, decision_at_utc=instant,
    )


class NBPArchiveDirectoryReviewTests(unittest.TestCase):
    def assert_research_only(self, report):
        self.assertEqual(report["schema"], "ISL_I7_NBP_ARCHIVE_DIRECTORY_CONSISTENCY_V01")
        self.assertEqual(report["qualified_model_series"], [])
        self.assertEqual(report["paper_candidates"], [])
        self.assertEqual(report["model_state"], "HOLD_CASH")
        self.assertFalse(report["same_day_use_allowed"])
        self.assertFalse(report["source_records_independently_authenticated"])
        self.assertFalse(report["historical_first_publication_timestamp_certified"])
        self.assertFalse(report["source_rights_independently_authorized"])
        self.assertFalse(report["market_execution_authorized"])
        self.assertFalse(report["total_return_series_qualified"])
        self.assertFalse(report["fx_conversion_performed"])
        self.assertFalse(report["price_levels_exported"])
        self.assertFalse(report["nbp_fx_values_exported"])
        self.assertFalse(report["source_manifest_created"])
        for key in ("orders_sent", "paper_fills", "financial_operations", "database_writes"):
            self.assertIs(type(report[key]), int)
            self.assertEqual(report[key], 0)
        self.assertRegex(report["receipt_sha256"], r"^[0-9a-f]{64}$")

    def test_matching_official_filename_convention_is_not_pit_attestation(self):
        out = check()
        self.assertEqual(out["status"], "LOCAL_RECORDS_CONSISTENT_PIT_AND_RIGHTS_UNVERIFIED")
        self.assertEqual(out["identical_table_a_day_and_number_pairs"], 3)
        self.assertEqual(out["directory_table_a_dates"], 3)
        self.assertTrue(out["requested_date_cross_checked"])
        self.assert_research_only(out)

    def test_same_day_publication_stays_blocked(self):
        out = check(instant="2026-10-30T23:59:59Z")
        self.assertEqual(out["status"], "CONSERVATIVE_DATE_LAG_NOT_PASSED")
        self.assertTrue(out["requested_date_cross_checked"])
        self.assert_research_only(out)

    def test_requested_day_not_in_api_window(self):
        out = check(day="2026-10-31", instant="2026-11-04T10:00:00Z")
        self.assertEqual(out["status"], "REQUESTED_DATE_NOT_IN_API_WINDOW")
        self.assertFalse(out["requested_date_cross_checked"])
        self.assert_research_only(out)

    def test_missing_exact_archive_entry_blocks_even_with_api_row(self):
        out = check(archive=DIR.replace(b"a214z261030\n", b""))
        self.assertEqual(out["status"], "REQUESTED_DATE_NOT_MATCHED_TO_ARCHIVE")
        self.assertEqual(out["api_dates_missing_in_directory"], 1)
        self.assert_research_only(out)

    def test_wrong_number_for_requested_day_blocks(self):
        out = check(archive=DIR.replace(b"a214z261030", b"a299z261030"))
        self.assertEqual(out["status"], "REQUESTED_DATE_NOT_MATCHED_TO_ARCHIVE")
        self.assertEqual(out["api_table_numbers_mismatched"], 1)
        self.assert_research_only(out)

    def test_partial_nonrequested_day_blocks_completion(self):
        out = check(archive=DIR.replace(b"a213z261029\n", b""))
        self.assertEqual(out["status"], "ARCHIVE_RECONCILIATION_INCOMPLETE")
        self.assertTrue(out["requested_date_cross_checked"])
        self.assert_research_only(out)

    def test_directory_can_include_other_known_tables_without_promoting_them(self):
        self.assertEqual(len(_archive_inventory(DIR, year=2026)), 3)
        self.assert_research_only(check())

    def test_duplicate_or_ambiguous_table_a_entries_rejected(self):
        for payload in (
            DIR + b"a214z261030\n",
            DIR + b"a215z261030\n",
        ):
            with self.subTest(payload=payload[-15:]), self.assertRaisesRegex(
                    NBPDirectoryError, "duplicate|multiple"):
                check(archive=payload)

    def test_unknown_or_malicious_directory_names_rejected(self):
        for bad in (b"not-an-NBP-file\n", b"../a222z261031\n",
                    b"a214z261030.xml\n", b"A214z261030\n"):
            with self.subTest(name=bad), self.assertRaisesRegex(
                    NBPDirectoryError, "syntax"):
                check(archive=DIR + bad)

    def test_invalid_month_day_and_wrong_year_rejected(self):
        for bad in (b"a008z261332\n", b"a008z260230\n", b"a008z251029\n"):
            with self.subTest(name=bad), self.assertRaises(NBPDirectoryError):
                check(archive=DIR + bad)

    def test_api_window_crossing_year_requires_separate_inventory(self):
        doc = sample()
        doc["rates"][-1]["effectiveDate"] = "2027-01-04"
        doc["rates"][-1]["no"] = "001/A/NBP/2027"
        with self.assertRaisesRegex(NBPDirectoryError, "cross-year"):
            check(snapshot=doc)

    def test_archive_year_must_match_requested_date(self):
        with self.assertRaisesRegex(NBPDirectoryError, "year and requested"):
            check(year=2025)

    def test_bad_archive_year_type_and_range_rejected(self):
        for year in (False, 2001, 2100, "2026", None):
            with self.subTest(year=year), self.assertRaises(NBPDirectoryError):
                check(year=year)

    def test_no_table_a_list_is_rejected(self):
        with self.assertRaisesRegex(NBPDirectoryError, "no official Table A"):
            check(archive=b"b213z261029\nc214z261030\n")

    def test_non_ascii_or_whitespace_only_directory_is_rejected(self):
        for doc in (b"", b"   ", b"a213z261029\n\n", b"\xff", b" a213z261029\n"):
            with self.subTest(doc=doc), self.assertRaises(NBPDirectoryError):
                check(archive=doc)

    def test_no_rate_values_ever_emitted_even_after_changing_rate(self):
        doc = sample()
        doc["rates"][1]["mid"] = 987654.12345
        out = check(snapshot=doc)
        self.assert_research_only(out)
        encoded = json.dumps(out)
        self.assertNotIn("987654", encoded)
        self.assertNotIn('"mid"', encoded)
        self.assertNotIn('"rates"', encoded)

    def test_repeatable_receipts_and_unmodified_inputs(self):
        doc = sample()
        before = deepcopy(doc)
        a = check(snapshot=doc)
        b = check(snapshot=deepcopy(doc))
        self.assertEqual(a, b)
        self.assertEqual(doc, before)
        changed = deepcopy(doc)
        changed["rates"][1]["mid"] = 4.01
        self.assertNotEqual(a["api_snapshot_canonical_sha256"],
                            check(snapshot=changed)["api_snapshot_canonical_sha256"])

    def test_local_archive_file_name_symlink_and_size_are_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f = root / "dir2026.txt"
            f.write_bytes(DIR)
            self.assertEqual(_read_directory(f, 2026), DIR)
            link = root / "dir2027.txt"
            link.symlink_to(f)
            with self.assertRaisesRegex(NBPDirectoryError, "regular"):
                _read_directory(link, 2027)
            with self.assertRaisesRegex(NBPDirectoryError, "named dir"):
                _read_directory(f, 2025)
            oversized = root / "dir2025.txt"
            oversized.write_bytes(b"x" * 180001)
            with self.assertRaisesRegex(NBPDirectoryError, "regular"):
                _read_directory(oversized, 2025)


if __name__ == "__main__":
    unittest.main()
