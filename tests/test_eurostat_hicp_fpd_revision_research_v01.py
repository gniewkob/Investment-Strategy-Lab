"""Strict offline synthetic CPI-revision research tests, not trading returns."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

from scripts.eurostat_hicp_fpd_revision_research_v01 import (
    HICPRevisionError, compare_revisions, _fpd_final_values, _window,
)
from tests.test_eurostat_hicp_macro_context_v01 import fixture as current_fixture
from tests.test_eurostat_hicp_fpd_schema_probe_v01 import example as fpd_fixture


def fpd():
    d = fpd_fixture()
    # Use the *actual* official Eurostat FPD release codes established on
    # Draft #121: FIN=Final, FLS=Flash. The probe's independent negative-test
    # fixture intentionally used R1/R2 placeholder codes.
    d["dimension"]["release"]["category"]["index"] = {"FIN": 0, "FLS": 1}
    d["dimension"]["release"]["category"]["label"] = {
        "FIN": "Final", "FLS": "Flash",
    }
    d["value"] = {
        "0": 99.3, "1": 100.1, "2": 101.4,
        "3": 19.9, "4": 20.1, "5": 21.4,
    }
    d["status"] = {"0": "p", "4": "e"}
    return d


def run(early=None, current=None, since="2026-07", until="2026-09"):
    return compare_revisions(
        fpd() if early is None else early,
        current_fixture() if current is None else current,
        since=since, until=until, observed_at_utc="2026-11-10T12:00:00Z")


class FPDFinalRevisionResearchTests(unittest.TestCase):
    def assert_safe(self, receipt):
        self.assertEqual(receipt["schema"],
                         "ISL_EUROSTAT_HICP_PL_FIRST_FINAL_REVISION_RESEARCH_V01")
        self.assertEqual(receipt["source"], "Eurostat")
        self.assertEqual(receipt["unit"], "I25_INDEX_2025_100")
        self.assertEqual(receipt["fpd_release_category"], "FIN")
        self.assertEqual(receipt["excluded_fpd_release_category"], "FLS")
        self.assertEqual(receipt["qualified_model_series"], [])
        self.assertEqual(receipt["paper_candidates"], [])
        self.assertEqual(receipt["model_state"], "HOLD_CASH")
        self.assertFalse(receipt["historical_point_in_time_certified"])
        self.assertFalse(receipt["historical_first_published_instant_authenticated"])
        self.assertFalse(receipt["full_historical_vintage_sequence_available"])
        self.assertFalse(receipt["market_execution_authorized"])
        self.assertFalse(receipt["source_manifest_created"])
        self.assertTrue(receipt["revision_not_investment_return"])
        for f in ("orders_sent", "paper_fills", "database_writes",
                  "financial_operations"):
            self.assertIs(type(receipt[f]), int)
            self.assertEqual(receipt[f], 0)

    def test_realistic_three_month_fpd_final_vs_latest_delta_only(self):
        x = run()
        self.assert_safe(x)
        self.assertEqual(x["status"], "REVISION_COMPARISON_RESEARCH_ONLY")
        self.assertEqual(x["month_count"], 3)
        self.assertEqual(x["comparable_month_count"], 3)
        self.assertEqual(x["nonzero_revision_months"], 1)
        self.assertEqual(x["max_absolute_revision_index_points"], "0.1")
        self.assertEqual([r["revision_index_points"] for r in x["rows"]],
                         ["0.0", "0.1", "0.0"])
        self.assertEqual(x["rows"][0]["first_final_flag"], "p")
        self.assertEqual(x["rows"][1]["latest_flag"], "e")

    def test_fls_flash_never_influences_final_delta(self):
        a = fpd()
        b = deepcopy(a)
        b["value"]["3"] = 900000
        b["value"]["4"] = 850000
        b["value"]["5"] = 750000
        receipt = run(b)
        self.assertEqual([r["revision_index_points"] for r in receipt["rows"]],
                         ["0.0", "0.1", "0.0"])
        self.assertNotEqual(run(a)["fpd_canonical_sha256"],
                            receipt["fpd_canonical_sha256"])
        self.assert_safe(receipt)

    def test_missing_fin_or_latest_is_explicitly_blocked(self):
        early = fpd()
        early["value"].pop("1")
        out = run(early)
        self.assertEqual(out["status"], "BLOCKED_INCOMPLETE_REVISIONS")
        self.assertEqual(out["missing_months"], ["2026-08"])
        self.assertEqual(out["comparable_month_count"], 2)
        self.assert_safe(out)
        latest = current_fixture(values=(99.3, None, 101.4))
        other = run(current=latest)
        self.assertEqual(other["missing_months"], ["2026-08"])
        self.assert_safe(other)

    def test_fpd_can_reverse_dimension_order(self):
        d = fpd()
        # Order of "release" and "time" axes changes multidimensional
        # flattening. Reencode payload so FIN values follow official axis.
        d["id"] = ["freq", "unit", "coicop18", "geo", "time", "release"]
        d["size"] = [1, 1, 1, 1, 3, 2]
        d["value"] = {"0": 99.3, "2": 100.1, "4": 101.4,
                      "1": 19.9, "3": 20.1, "5": 21.4}
        d["status"] = {"0": "p"}
        out = run(d)
        self.assertEqual(out["nonzero_revision_months"], 1)
        self.assertEqual(out["rows"][1]["revision_index_points"], "0.1")
        self.assert_safe(out)

    def test_wrong_country_unit_aggregate_or_freq_rejected(self):
        for key, value in (("geo", "DE"), ("unit", "I15"),
                           ("coicop18", "CP00"), ("freq", "A")):
            d = fpd()
            d["dimension"][key]["category"]["index"] = {value: 0}
            with self.subTest(name=key), self.assertRaisesRegex(
                    HICPRevisionError, "mismatch"):
                run(d)

    def test_release_category_missing_or_invented_rejected(self):
        d = fpd()
        d["dimension"]["release"]["category"]["index"] = {"FIN": 0, "PIT": 1}
        with self.assertRaisesRegex(HICPRevisionError, "FIN/FLS"):
            run(d)
        d = fpd()
        d["dimension"]["release"]["category"]["label"]["FIN"] = "Certified"
        with self.assertRaisesRegex(HICPRevisionError, "labels"):
            run(d)

    def test_fin_and_flash_reversed_indices_are_supported(self):
        d = fpd()
        d["dimension"]["release"]["category"]["index"] = {"FLS": 0, "FIN": 1}
        d["value"] = {
            "0": 19.9, "1": 20.1, "2": 21.4,
            "3": 99.3, "4": 100.1, "5": 101.4,
        }
        d["status"] = {}
        result = run(d)
        self.assertEqual(result["nonzero_revision_months"], 1)
        self.assert_safe(result)

    def test_wrong_or_incomplete_time_window_rejected(self):
        d = fpd()
        d["dimension"]["time"]["category"]["index"] = {
            "2026-07": 0, "2026-09": 1, "2026-10": 2,
        }
        with self.assertRaisesRegex(HICPRevisionError, "month gap|requested"):
            run(d)
        with self.assertRaisesRegex(HICPRevisionError, "window"):
            run(until="2026-10")

    def test_mismatched_minr_units_and_months_rejected(self):
        c = current_fixture()
        c["dimension"]["unit"]["category"]["index"] = {"I15": 0}
        with self.assertRaisesRegex(HICPRevisionError, "latest-vintage"):
            run(current=c)
        c = current_fixture(months=("2026-07", "2026-09", "2026-10"))
        with self.assertRaisesRegex(HICPRevisionError, "latest-vintage"):
            run(current=c)

    def test_nan_negative_boolean_and_bad_fpd_index_rejected(self):
        for bad in (float("nan"), float("inf"), -1, 0, True, "unknown"):
            d = fpd()
            d["value"]["1"] = bad
            with self.subTest(value=str(bad)), self.assertRaises(
                    HICPRevisionError):
                run(d)

    def test_sparse_out_of_bounds_and_unknown_dimension_rejected(self):
        d = fpd()
        d["value"]["100"] = 12.5
        with self.assertRaisesRegex(HICPRevisionError, "sparse value key"):
            run(d)
        d = fpd()
        d["id"].append("broker")
        d["size"].append(1)
        d["dimension"]["broker"] = {"category": {"index": {"LIVE": 0}}}
        with self.assertRaisesRegex(HICPRevisionError, "six-dimensional"):
            run(d)

    def test_invalid_fpd_status_key_and_value_rejected(self):
        d = fpd()
        d["status"]["100"] = "s"
        with self.assertRaisesRegex(HICPRevisionError, "status key/flag"):
            run(d)
        d = fpd()
        d["status"]["0"] = True
        with self.assertRaisesRegex(HICPRevisionError, "status key/flag"):
            run(d)

    def test_january_2026_restoration_exception_requires_review(self):
        first = fpd()
        first["dimension"]["time"]["category"]["index"] = {
            "2026-01": 0, "2026-02": 1, "2026-03": 2,
        }
        latest = current_fixture(months=("2026-01", "2026-02", "2026-03"))
        result = run(first, latest, since="2026-01", until="2026-03")
        self.assertEqual(result["status"],
                         "REVIEW_REQUIRED_KNOWN_JAN_2026_FPD_EXCEPTION")
        self.assertEqual(result["exception_months"], ["2026-01"])
        self.assertFalse(result["rows"][0]["included_in_revision_summary"])
        self.assertEqual(result["comparable_month_count"], 2)
        self.assert_safe(result)

    def test_out_of_scope_months_and_timestamp_rejected(self):
        for a, b in (("2025-12", "2026-03"), ("2026-09", "2026-07"),
                     ("2026-01", "2028-05"), ("2026-13", "2026-14")):
            with self.subTest(a=a, b=b), self.assertRaises(HICPRevisionError):
                _window(a, b)
        for instant in ("2026-11-10T12:00:00", "2026-11-10T13:00:00+01:00",
                        "not-time", None):
            with self.subTest(instant=instant), self.assertRaises(HICPRevisionError):
                compare_revisions(fpd(), current_fixture(), since="2026-07",
                                  until="2026-09", observed_at_utc=instant)

    def test_cannot_promote_forged_market_metadata_in_input(self):
        first = fpd()
        latest = current_fixture()
        first["historical_pit_certified"] = True
        first["orders_sent"] = 5
        latest["qualified_model_series"] = ["GLOBAL_EQUITY_TR_PLN"]
        result = run(first, latest)
        self.assert_safe(result)
        self.assertNotIn("GLOBAL_EQUITY_TR_PLN", json.dumps(result))

    def test_receipt_deterministic_immutable_and_no_original_levels_emitted(self):
        early, later = fpd(), current_fixture()
        a = run(early, later)
        b = run(deepcopy(early), deepcopy(later))
        self.assertEqual(a, b)
        self.assertEqual(early, fpd())
        self.assertEqual(later, current_fixture())
        rendered = json.dumps(a)
        self.assertNotIn("99.3", rendered)
        self.assertNotIn("100.2", rendered)
        self.assertNotIn("101.4", rendered)
        self.assertEqual(a["observed_at_utc"], "2026-11-10T12:00:00+00:00")
        self.assert_safe(a)


if __name__ == "__main__":
    unittest.main()
