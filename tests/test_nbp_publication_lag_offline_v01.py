"""I6 offline NBP Table A date-lag and no-price-leakage tests; synthetic values."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import json
import tempfile
import unittest

from scripts.nbp_publication_lag_offline_v01 import (
    NBPDateLagError, _read_local, assess_nbp_publication_lag, SCHEMA,
)


def sample():
    return {
        "table": "A",
        "currency": "dolar amerykanski",
        "code": "USD",
        "rates": [
            {"no": "213/A/NBP/2026", "effectiveDate": "2026-10-29", "mid": 3.91},
            {"no": "214/A/NBP/2026", "effectiveDate": "2026-10-30", "mid": 3.92},
            {"no": "215/A/NBP/2026", "effectiveDate": "2026-11-02", "mid": 3.93},
        ],
    }


def check(snapshot=None, *, when="2026-10-31T00:00:00Z", date="2026-10-30"):
    return assess_nbp_publication_lag(
        sample() if snapshot is None else snapshot,
        requested_effective_date=date, decision_at_utc=when)


class NBPPublicationLagOfflineTests(unittest.TestCase):
    def assert_nonpromoting(self, result):
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["source_kind"], "NBP_USDPLN_TABLE_A_MID_NON_EXECUTABLE_FX")
        self.assertEqual(result["qualified_model_series"], [])
        self.assertEqual(result["paper_candidates"], [])
        self.assertEqual(result["model_state"], "HOLD_CASH")
        self.assertFalse(result["source_manifest_created"])
        self.assertFalse(result["fx_conversion_performed"])
        self.assertFalse(result["forward_fill_performed"])
        self.assertFalse(result["same_day_use_allowed"])
        self.assertFalse(result["independently_certified_historical_pit"])
        self.assertFalse(result["independently_verified_first_publication_instant"])
        self.assertFalse(result["independently_certified_source_rights"])
        self.assertFalse(result["eligible_as_model_total_return_series"])
        self.assertFalse(result["market_execution_authorized"])
        self.assertFalse(result["rate_values_in_receipt"])
        for key in ("orders_sent", "paper_fills", "financial_operations",
                    "database_writes"):
            self.assertIs(type(result[key]), int)
            self.assertEqual(result[key], 0)
        self.assertRegex(result["receipt_sha256"], r"^[0-9a-f]{64}$")

    def test_published_day_at_2300_utc_is_still_blocked(self):
        r = check(when="2026-10-30T23:00:00Z")
        self.assertEqual(r["status"], "NOT_YET_PASSED_CONSERVATIVE_NEXT_DAY_LAG")
        self.assertEqual(r["research_not_before_utc"], "2026-10-31T00:00:00+00:00")
        self.assert_nonpromoting(r)

    def test_first_second_of_next_utc_day_is_not_pit_certification(self):
        r = check(when="2026-10-31T00:00:00Z")
        self.assertEqual(r["status"], "DATE_LAG_PASSED_NOT_HISTORICAL_PIT_CERTIFIED")
        self.assertTrue(r["exact_publication_date_present"])
        self.assert_nonpromoting(r)

    def test_weekend_after_friday_is_not_execution_eligibility(self):
        r = check(when="2026-11-01T13:00:00Z")
        self.assertEqual(r["status"], "DATE_LAG_PASSED_NOT_HISTORICAL_PIT_CERTIFIED")
        self.assert_nonpromoting(r)

    def test_explicit_missing_effective_date_does_not_forward_fill(self):
        r = check(date="2026-10-31", when="2026-11-03T10:00:00Z")
        self.assertEqual(r["status"], "NO_EXACT_SOURCE_PUBLICATION_DATE")
        self.assertFalse(r["exact_publication_date_present"])
        self.assert_nonpromoting(r)

    def test_future_publication_relative_to_decision_is_blocked(self):
        r = check(date="2026-11-02", when="2026-10-30T14:00:00Z")
        self.assertEqual(r["status"], "NOT_YET_PASSED_CONSERVATIVE_NEXT_DAY_LAG")
        self.assert_nonpromoting(r)

    def test_rate_values_never_leak_to_metadata_receipt(self):
        doc = sample()
        doc["rates"][1]["mid"] = 888123.4567
        r = check(doc)
        self.assert_nonpromoting(r)
        self.assertNotIn("888123", json.dumps(r))
        self.assertNotIn('"mid"', json.dumps(r))
        self.assertNotIn('"rates"', json.dumps(r))
        self.assertEqual(r["source_rows_examined"], 3)

    def test_canonical_receipt_deterministic_and_input_unchanged(self):
        doc = sample()
        before = deepcopy(doc)
        a = check(doc)
        b = check(deepcopy(doc))
        self.assertEqual(a, b)
        self.assertEqual(doc, before)

    def test_changed_source_changes_snapshot_sha_but_not_qualification(self):
        a = check()
        changed = sample()
        changed["rates"][1]["mid"] = 9.50
        b = check(changed)
        self.assertNotEqual(a["canonical_local_snapshot_sha256"],
                            b["canonical_local_snapshot_sha256"])
        self.assertEqual(a["status"], b["status"])
        self.assert_nonpromoting(b)

    def test_nbp_table_c_and_other_currency_rejected(self):
        for key, value in (("table", "C"), ("table", "B"), ("code", "EUR")):
            d = sample()
            d[key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(
                    NBPDateLagError, "Table A"):
                check(d)

    def test_nbp_source_no_mismatch_rejected(self):
        for bad in ("214/C/NBP/2026", "214/A/NBP/2025",
                    "NOT_A_REAL_NBP_NUMBER", "", None):
            d = sample()
            d["rates"][1]["no"] = bad
            with self.subTest(bad=bad), self.assertRaisesRegex(
                    NBPDateLagError, "number/year"):
                check(d)

    def test_duplicate_or_unsorted_dates_rejected(self):
        for offset in ("2026-10-29", "2026-10-27"):
            d = sample()
            d["rates"][1]["effectiveDate"] = offset
            with self.subTest(offset=offset), self.assertRaisesRegex(
                    NBPDateLagError, "unsorted"):
                check(d)

    def test_non_utc_and_ambiguous_time_rejected(self):
        for instant in ("2026-10-31T00:00:00",
                        "2026-10-31T01:00:00+01:00",
                        "2026-10-31", "not-a-date", None):
            with self.subTest(instant=instant), self.assertRaises(
                    NBPDateLagError):
                check(when=instant)

    def test_bad_requested_date_and_out_of_range_rejected(self):
        for requested in ("2026-13-01", "2026-02-30", "not-date",
                          "2002-01-01", "9999-12-31"):
            with self.subTest(day=requested), self.assertRaises(NBPDateLagError):
                check(date=requested)

    def test_bad_or_nonfinite_mid_rejected(self):
        for bad in (-1, 0, "4.25", False, None, float("nan"), float("inf")):
            d = sample()
            d["rates"][0]["mid"] = bad
            with self.subTest(bad=str(bad)), self.assertRaises(
                    NBPDateLagError):
                check(d)

    def test_json_native_float_and_integer_mid_accepted_only_as_reference(self):
        d = sample()
        d["rates"][0]["mid"] = 4
        d = json.loads(json.dumps(d))
        self.assert_nonpromoting(check(d))

    def test_unknown_nested_fields_or_executable_promotion_rejected(self):
        for scope in ("root", "row"):
            d = sample()
            if scope == "root":
                d["model_source_qualified"] = True
            else:
                d["rates"][0]["trading_authorized"] = True
            with self.subTest(scope=scope), self.assertRaises(NBPDateLagError):
                check(d)

    def test_too_many_or_zero_rates_rejected(self):
        d = sample()
        d["rates"] = []
        with self.assertRaisesRegex(NBPDateLagError, "1-93"):
            check(d)
        d = sample()
        d["rates"] = d["rates"] * 32
        with self.assertRaisesRegex(NBPDateLagError, "1-93"):
            check(d)

    def test_local_symlink_and_oversized_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f = root / "nbp.json"
            f.write_text(json.dumps(sample()))
            link = root / "link.json"
            link.symlink_to(f)
            with self.assertRaisesRegex(NBPDateLagError, "regular local"):
                _read_local(link)
            huge = root / "huge.json"
            huge.write_bytes(b" " * 250_001)
            with self.assertRaisesRegex(NBPDateLagError, "bounded regular"):
                _read_local(huge)
            self.assertEqual(_read_local(f), sample())


if __name__ == "__main__":
    unittest.main()
