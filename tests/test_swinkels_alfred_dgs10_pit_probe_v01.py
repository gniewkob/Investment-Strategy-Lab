"""ALFRED DGS10 PIT probe: offline synthetic-only verification."""
import json
import unittest

from scripts.swinkels_alfred_dgs10_pit_probe_v01 import (
    CHECKS, SourceUnavailable, compare_archived_samples, parse_snapshot,
    validate_api_key,
)


def sample_json(date="2020-01-31", asof="2020-02-15", value="1.51"):
    return json.dumps({
        "observations": [{
            "date": date, "realtime_start": asof, "realtime_end": asof, "value": value,
        }]
    }).encode()


def synthetic_pairs(mismatch=False):
    items = {}
    ods = {}
    for i, (month, observed, asof) in enumerate(CHECKS):
        val = 2.0 + i
        items[month] = {"date": observed, "asof": asof, "value": val}
        ods[month] = {"yield": val / 100}
    if mismatch:
        ods[CHECKS[0][0]]["yield"] = 0.05
    return items, ods


class ALFREDSourcePITTests(unittest.TestCase):
    def test_valid_key_format(self):
        self.assertEqual(validate_api_key("a" * 32), "a" * 32)

    def test_invalid_key_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "format"):
            validate_api_key("bad")

    def test_valid_archived_observation(self):
        self.assertEqual(parse_snapshot(sample_json(), "2020-01-31", "2020-02-15"), 1.51)

    def test_current_mode_asof_mismatch_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "as-of"):
            parse_snapshot(sample_json(asof="2026-11-10"), "2020-01-31", "2020-02-15")

    def test_wrong_observation_day_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "date mismatch"):
            parse_snapshot(sample_json(date="2020-01-30"), "2020-01-31", "2020-02-15")

    def test_missing_daily_value_rejected(self):
        with self.assertRaisesRegex(SourceUnavailable, "missing or invalid"):
            parse_snapshot(sample_json(value="."), "2020-01-31", "2020-02-15")

    def test_ambiguous_multiple_revisions_rejected(self):
        message = json.dumps({"observations": [
            {"date": "2020-01-31", "realtime_start": "2020-02-15",
             "realtime_end": "2020-02-15", "value": "1.51"},
            {"date": "2020-01-31", "realtime_start": "2020-02-15",
             "realtime_end": "2020-02-15", "value": "1.51"},
        ]}).encode()
        with self.assertRaisesRegex(SourceUnavailable, "one observation"):
            parse_snapshot(message, "2020-01-31", "2020-02-15")

    def test_incomplete_scope_rejected(self):
        items, original = synthetic_pairs()
        del items["2021-06"]
        with self.assertRaisesRegex(SourceUnavailable, "scope incomplete"):
            compare_archived_samples(items, original)

    def test_month_asof_swap_rejected(self):
        items, original = synthetic_pairs()
        items["2021-06"]["asof"] = "2026-11-10"
        with self.assertRaisesRegex(SourceUnavailable, "binding mismatch"):
            compare_archived_samples(items, original)

    def test_matches_do_not_qualify_pit(self):
        items, original = synthetic_pairs()
        result = compare_archived_samples(items, original)
        self.assertEqual(result["archived_asof_sample_count"], 3)
        self.assertTrue(all(x["comparison_to_original_ods"] == "MATCH" for x in result["samples"]))
        self.assertFalse(result["availability_at_month_end_decision_certified"])
        self.assertFalse(result["historical_pit_certified"])
        self.assertFalse(result["original_ods_monthly_aggregation_method_certified"])
        self.assertEqual(result["qualified_model_series"], [])
        self.assertEqual(result["model_state"], "HOLD_CASH")
        self.assertEqual(result["financial_operations"], 0)

    def test_value_mismatch_does_not_qualify(self):
        items, original = synthetic_pairs(mismatch=True)
        result = compare_archived_samples(items, original)
        self.assertEqual(result["samples"][0]["comparison_to_original_ods"], "NOT_MATCHED")
        self.assertFalse(result["historical_pit_certified"])


if __name__ == "__main__":
    unittest.main()
