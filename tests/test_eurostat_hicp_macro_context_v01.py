"""Eurostat HICP JSON-stat research-only tests (entirely synthetic values)."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

from scripts.eurostat_hicp_macro_context_v01 import (
    HICPContextError, _fetch, _query, _read, inspect_hicp,
)


def fixture(*, months=("2026-01", "2026-02", "2026-03"),
            values=(99.3, 100.2, 101.4),
            order=("freq", "unit", "coicop18", "geo", "time")):
    fixed = {
        "freq": {"M": 0},
        "unit": {"I25": 0},
        "coicop18": {"TOTAL": 0},
        "geo": {"PL": 0},
    }
    categories = {**fixed, "time": {m: i for i, m in enumerate(months)}}
    return {
        "version": "2.0", "class": "dataset", "source": "ESTAT",
        "updated": "2026-04-16T11:00:00+0200",
        "id": list(order),
        "size": [len(categories[k]) for k in order],
        "dimension": {k: {"label": k, "category": {
            "index": categories[k],
            "label": {name: name for name in categories[k]},
        }} for k in order},
        "value": {str(i): value for i, value in enumerate(values) if value is not None},
        "status": {"1": "e"},
    }


def inspect(data=None, *, since="2026-01", until="2026-03",
            scope="LOCAL_OFFLINE_REVIEW"):
    return inspect_hicp(
        fixture() if data is None else data, since=since, until=until,
        retrieval_scope=scope)


class EurostatHICPContextTests(unittest.TestCase):
    def assert_no_promotion(self, receipt):
        self.assertEqual(receipt["schema"], "ISL_EUROSTAT_HICP_PL_MACRO_CONTEXT_V01")
        self.assertEqual(receipt["country"], "PL")
        self.assertEqual(receipt["measure_unit"], "I25_INDEX_2025_100")
        self.assertEqual(receipt["indicator_type"], "CONSUMER_PRICE_INDEX")
        self.assertEqual(receipt["qualified_model_series"], [])
        self.assertEqual(receipt["paper_candidates"], [])
        self.assertEqual(receipt["model_state"], "HOLD_CASH")
        for field in ("historical_first_release_captured",
                      "historical_point_in_time_certified",
                      "first_released_fpd_reconciled",
                      "price_index_as_asset_return",
                      "source_manifest_created"):
            self.assertFalse(receipt[field])
        for field in ("orders_sent", "financial_operations", "paper_fills",
                      "database_writes"):
            self.assertIs(type(receipt[field]), int)
            self.assertEqual(receipt[field], 0)
        self.assertRegex(receipt["receipt_sha256"], r"^[0-9a-f]{64}$")

    def test_three_months_2025_base_is_macro_only(self):
        r = inspect()
        self.assertEqual(r["status"], "AVAILABLE_CONTEXT_NOT_HISTORICAL_PIT")
        self.assertEqual(r["observed_month_count"], 3)
        self.assertEqual(r["available_month_count"], 3)
        self.assertEqual([x["index_2025_100"] for x in r["observations"]],
                         ["99.3", "100.2", "101.4"])
        self.assertEqual(r["observations"][1]["status"], "e")
        self.assert_no_promotion(r)

    def test_sparse_missing_observation_explicitly_blocks_completeness(self):
        data = fixture(values=(99.3, None, 101.4))
        r = inspect(data)
        self.assertEqual(r["status"], "BLOCKED_INCOMPLETE_CONTEXT")
        self.assertEqual(r["missing_months"], ["2026-02"])
        self.assertEqual(r["available_month_count"], 2)
        self.assert_no_promotion(r)

    def test_arbitrary_dimension_order_supported(self):
        data = fixture(order=("time", "freq", "coicop18", "unit", "geo"))
        self.assert_no_promotion(inspect(data))
        self.assertEqual(inspect(data)["observations"][-1]["index_2025_100"],
                         "101.4")

    def test_deterministic_receipt_does_not_mutate_provider_json(self):
        data = fixture()
        original = deepcopy(data)
        a = inspect(data)
        self.assertEqual(a, inspect(deepcopy(data)))
        self.assertEqual(data, original)
        self.assertNotEqual(a["receipt_sha256"], a["source_payload_canonical_sha256"])

    def test_source_updated_is_not_first_published_at(self):
        data = fixture()
        data["updated"] = "2031-01-01T00:00:00Z"
        r = inspect(data)
        self.assertEqual(r["provider_reported_last_update"], data["updated"])
        self.assertFalse(r["historical_first_release_captured"])
        self.assert_no_promotion(r)

    def test_wrong_geo_or_unit_or_frequency_or_aggregate_rejected(self):
        for key, new in (("geo", "DE"), ("unit", "I15"),
                         ("freq", "A"), ("coicop18", "CP00")):
            data = fixture()
            data["dimension"][key]["category"]["index"] = {new: 0}
            with self.subTest(key=key), self.assertRaisesRegex(
                    HICPContextError, "unexpected unit/country/measure"):
                inspect(data)

    def test_alternative_data_class_source_version_rejected(self):
        for key, new in (("version", "1.0"), ("class", "table"),
                         ("source", "VENDOR"), ("source", "")):
            data = fixture()
            data[key] = new
            with self.subTest(key=key), self.assertRaises(HICPContextError):
                inspect(data)

    def test_extra_release_dim_or_missing_time_dim_rejected(self):
        data = fixture()
        data["id"].append("release")
        data["size"].append(1)
        data["dimension"]["release"] = {"category": {"index": {"ORIGINAL": 0}}}
        with self.assertRaisesRegex(HICPContextError, "exact HICP dimensions"):
            inspect(data)
        data = fixture()
        data["id"].remove("time")
        data["size"].pop()
        data["dimension"].pop("time")
        with self.assertRaisesRegex(HICPContextError, "exact HICP dimensions"):
            inspect(data)

    def test_sparse_out_of_range_and_wrong_dense_shape_rejected(self):
        data = fixture()
        data["value"]["999"] = 140
        with self.assertRaisesRegex(HICPContextError, "sparse index positions"):
            inspect(data)
        data = fixture()
        data["value"] = [99.3]
        with self.assertRaisesRegex(HICPContextError, "dense data vector"):
            inspect(data)

    def test_nonsequential_observations_rejected(self):
        data = fixture(months=("2026-01", "2026-03", "2026-04"))
        with self.assertRaisesRegex(HICPContextError, "chronological gaps"):
            inspect(data, until="2026-04")

    def test_response_month_window_mismatch_rejected(self):
        with self.assertRaisesRegex(HICPContextError, "cover requested"):
            inspect(until="2026-04")
        with self.assertRaisesRegex(HICPContextError, "outside query window"):
            inspect(since="2026-02")

    def test_bool_negative_nan_and_invalid_value_rejected(self):
        for value in (True, -1, 0, float("nan"), float("inf"), "bad"):
            data = fixture()
            data["value"]["1"] = value
            with self.subTest(value=str(value)), self.assertRaises(
                    HICPContextError):
                inspect(data)

    def test_category_indices_must_be_exact_and_unique(self):
        data = fixture()
        data["dimension"]["time"]["category"]["index"]["2026-03"] = 1
        with self.assertRaisesRegex(HICPContextError, "category positions"):
            inspect(data)
        data = fixture()
        data["dimension"]["time"]["category"]["index"]["2026-04"] = 3
        with self.assertRaisesRegex(HICPContextError, "categorical entries"):
            inspect(data)

    def test_forged_qualified_source_field_is_not_trusted(self):
        data = fixture()
        data["historical_pit_certified"] = True
        data["financial_operations"] = 99
        r = inspect(data)
        self.assert_no_promotion(r)
        self.assertNotIn('"financial_operations": 99', json.dumps(r))

    def test_bounded_explicit_fixed_official_query(self):
        url = _query("2026-01", "2026-03")
        self.assertTrue(url.startswith(
            "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_minr?"))
        self.assertIn("geo=PL", url)
        self.assertIn("unit=I25", url)
        self.assertIn("coicop18=TOTAL", url)
        self.assertIn("sinceTimePeriod=2026-01", url)
        self.assertIn("untilTimePeriod=2026-03", url)

    def test_out_of_bounds_and_future_query_rejected(self):
        for start, end in (
            ("2020-01", "2026-03"),
            ("2026-03", "2026-01"),
            ("2026-11", "2026-12"),
            ("2026-02-01", "2026-03"),
            ("2026-13", "2026-12"),
        ):
            with self.subTest(start=start, end=end), self.assertRaises(
                    HICPContextError):
                _query(start, end)

    def test_network_fetch_does_not_accept_arbitrary_url(self):
        for url in ("https://example.com/", "file:///etc/passwd", "http://ec.europa.eu/"):
            with self.subTest(url=url), self.assertRaisesRegex(
                    HICPContextError, "only official fixed Eurostat"):
                _fetch(url)

    def test_local_file_symlink_and_size_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            good = root / "hicp.json"
            good.write_text(json.dumps(fixture()))
            self.assertEqual(_read(good), fixture())
            symlink = root / "link.json"
            symlink.symlink_to(good)
            with self.assertRaisesRegex(HICPContextError, "bounded regular"):
                _read(symlink)
            oversized = root / "large.json"
            oversized.write_bytes(b"x" * 1_000_001)
            with self.assertRaisesRegex(HICPContextError, "bounded regular"):
                _read(oversized)


if __name__ == "__main__":
    unittest.main()
