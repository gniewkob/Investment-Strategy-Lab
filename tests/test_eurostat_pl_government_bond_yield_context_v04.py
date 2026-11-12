"""Original-shape Eurostat MCBY/PL yield reference; offline/negative acceptance."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import unittest
from unittest.mock import patch

from scripts.eurostat_pl_government_bond_yield_context_v04 import (
    PLYieldContextBlocked, parse_original_yields, SINCE, UNTIL, MAX_MONTHS,
)

OBSERVED = datetime(2026, 11, 12, 21, 30, tzinfo=timezone.utc)


def months():
    y, m = 2021, 11
    out = []
    for _ in range(MAX_MONTHS):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def original_shape(*, dims=("freq", "int_rt", "geo", "time")):
    calendar = months()
    assert calendar[0] == SINCE and calendar[-1] == UNTIL
    catalog = {"freq": {"M": 0}, "int_rt": {"MCBY": 0},
               "geo": {"PL": 0}, "time": {date: i for i, date in enumerate(calendar)}}
    return {
        "version": "2.0", "class": "dataset", "source": "ESTAT",
        "updated": "2026-11-12T11:00:00+0100",
        "id": list(dims),
        "size": [len(catalog[x]) for x in dims],
        "dimension": {k: {"category": {"index": catalog[k]}} for k in dims},
        "value": {str(i): round(4 + i * 0.01, 4) for i in range(MAX_MONTHS)},
        "status": {"1": "p"},
    }


def parse(data=None, *, at=OBSERVED):
    return parse_original_yields(
        json.dumps(data if data is not None else original_shape()).encode(),
        observed_at=at)


class PLYieldContextTests(unittest.TestCase):
    def test_original_shape_59_months_yield_semantics_provenance(self):
        r = parse()
        self.assertEqual(r["observed_months"], 59)
        self.assertEqual((r["first_month"], r["last_month"]), (SINCE, UNTIL))
        self.assertEqual(r["source_unit"], "PERCENT_PER_ANNUM")
        self.assertEqual(r["interest_rate_code"], "MCBY")
        self.assertEqual(r["country"], "PL")
        self.assertEqual(r["min_yield_pct_per_annum"], "4.0")
        self.assertEqual(r["max_yield_pct_per_annum"], "4.58")
        self.assertEqual(r["mean_yield_pct_per_annum"], "4.2900")
        self.assertEqual(r["max_abs_adjacent_month_level_change_bps"], "1.00")
        self.assertEqual(r["source_statistical_flags_count"], {"p": 1})
        self.assertRegex(r["original_response_sha256"], r"^[a-f0-9]{64}$")
        self.assertRegex(r["receipt_sha256"], r"^[a-f0-9]{64}$")
        self.assertFalse(r["historical_pit_certified"])
        self.assertFalse(r["bond_holding_period_return_observed"])
        self.assertFalse(r["tbsp_income_index_observed"])
        self.assertEqual(r["qualified_model_series"], [])
        self.assertEqual(r["legacy_m1_m2_m3"], "INSUFFICIENT_DATA_HOLD_CASH")
        self.assertEqual(r["financial_operations"], 0)
        self.assertEqual(r["database_writes"], 0)
        self.assertEqual(r["orders_sent"], 0)
        self.assertNotIn('"observations"', json.dumps(r))
        self.assertNotIn('"value":', json.dumps(r))

    def test_source_current_vintage_not_historical_first_release(self):
        d = original_shape()
        d["updated"] = "2026-11-12T11:00:00+0100"
        r = parse(d)
        self.assertTrue(r["present_snapshot_not_original_historic_vintages"])
        self.assertFalse(r["historical_first_available_at_verified"])
        self.assertEqual(r["provider_reported_updated_not_first_release"], d["updated"])

    def test_deterministic_same_original_bytes_except_fetch_time(self):
        self.assertEqual(parse(), parse())
        d = original_shape()
        d["status"]["1"] = "e"
        self.assertNotEqual(parse(d)["original_response_sha256"],
                            parse()["original_response_sha256"])

    def test_dimension_order_independent(self):
        d = original_shape(dims=("time", "geo", "freq", "int_rt"))
        self.assertEqual(parse(d)["mean_yield_pct_per_annum"], "4.2900")

    def test_missing_month_and_index_hole_fail_closed(self):
        d = original_shape()
        d["dimension"]["time"]["category"]["index"].pop("2025-01")
        d["size"][-1] -= 1
        with self.assertRaises(PLYieldContextBlocked):
            parse(d)
        d = original_shape()
        d["dimension"]["time"]["category"]["index"]["2024-11"] = 900
        with self.assertRaises(PLYieldContextBlocked):
            parse(d)

    def test_sparse_missing_and_invalid_index_fail_closed(self):
        d = original_shape()
        d["value"].pop("8")
        with self.assertRaisesRegex(PLYieldContextBlocked, "MISSING"):
            parse(d)
        d = original_shape()
        d["value"]["9999"] = 8
        with self.assertRaisesRegex(PLYieldContextBlocked, "VECTOR"):
            parse(d)

    def test_wrong_geo_indicator_frequency_and_source_fail_closed(self):
        for key, bad in (("geo", "DE"), ("int_rt", "OTHER"), ("freq", "A")):
            d = original_shape()
            d["dimension"][key]["category"]["index"] = {bad: 0}
            with self.subTest(key=key), self.assertRaisesRegex(
                    PLYieldContextBlocked, "WRONG_COUNTRY"):
                parse(d)
        d = original_shape()
        d["source"] = "MIRROR"
        with self.assertRaisesRegex(PLYieldContextBlocked, "UNSUPPORTED_OFFICIAL"):
            parse(d)

    def test_false_values_rejected_not_silently_zero_filled(self):
        for bad in (None, True, float("nan"), float("inf"), "NA", 95, -30):
            d = original_shape()
            d["value"]["5"] = bad
            with self.subTest(bad=str(bad)), self.assertRaises(PLYieldContextBlocked):
                parse(d)

    def test_status_flag_validation(self):
        d = original_shape()
        d["status"]["1"] = "not-a-valid-statistic-flag"
        with self.assertRaises(PLYieldContextBlocked):
            parse(d)
        d = original_shape()
        d["status"]["10000"] = "p"
        with self.assertRaisesRegex(PLYieldContextBlocked, "VECTOR"):
            parse(d)

    def test_future_month_time_and_provider_update_rejected(self):
        with self.assertRaisesRegex(PLYieldContextBlocked, "FUTURE"):
            parse(at=datetime(2025, 1, 1, tzinfo=timezone.utc))
        d = original_shape()
        d["updated"] = "2030-01-01T00:00:00Z"
        with self.assertRaisesRegex(PLYieldContextBlocked, "PROVIDER_TIMESTAMP"):
            parse(d)
        with self.assertRaisesRegex(PLYieldContextBlocked, "CLOCK_REQUIRED"):
            parse(at=datetime(2026, 11, 12))

    def test_wrong_base_jsonstat_and_oversize_rejected(self):
        for raw in (b"", b"not-json", b"{}", b"x" * 600001):
            with self.subTest(size=len(raw)), self.assertRaises(PLYieldContextBlocked):
                parse_original_yields(raw, observed_at=OBSERVED)

    def test_no_network_or_model_operation_in_parser(self):
        def deny(*args, **kwargs):
            raise AssertionError("Parser attempted to use network")
        with patch("socket.socket.connect", side_effect=deny):
            self.assertEqual(parse()["financial_operations"], 0)


if __name__ == "__main__":
    unittest.main()
